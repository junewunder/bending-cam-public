import { AppState, type NativeEventSubscription } from 'react-native';
import { ConnectionPriority, type Subscription } from 'react-native-ble-plx';

import { type Connection, connect, manager, requestBlePermissions, scan } from '../ble/client';
import { CAMERA } from '../config/camera';
import { loadPrefs, savePrefs } from '../store';
import { Emitter, IDLE, type Link, type LinkState, type ScanHit } from './link';
import { type Message, Reader, type Request, encode } from './protocol';

const GRACE_MS = 8000;
const BACKOFF_MS = [500, 1000, 2000, 4000, 8000];
const STABLE_MS = 15_000;
const RSSI_MS = 2000;

export class BleLink implements Link {
  private s: LinkState = IDLE;
  private changes = new Emitter<LinkState>();
  private messages = new Emitter<Message>();
  private stillPackets = new Emitter<Uint8Array>();
  private fast = false;
  private reader = new Reader((m) => this.messages.emit(m));

  private running = false;
  private target: { id: string; name: string | null } | null = null;
  private conn: Connection | null = null;
  private connSubs: Subscription[] = [];
  private stopScan: (() => void) | null = null;
  private powerSub: Subscription | null = null;
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private rssiTimer: ReturnType<typeof setInterval> | null = null;
  private attempts = 0;
  private connectedAt = 0;
  private waiting: string | null = null;
  private appState: NativeEventSubscription | null = null;

  state() {
    return this.s;
  }

  watch(l: (s: LinkState) => void) {
    return this.changes.add(l);
  }

  onMessage(l: (m: Message) => void) {
    return this.messages.add(l);
  }

  async send(req: Request) {
    if (!this.conn || !this.s.hasSettings) throw new Error('No settings link.');
    await this.conn.request(CAMERA.settings, encode(req));
  }

  onStillPacket(l: (p: Uint8Array) => void) {
    return this.stillPackets.add(l);
  }

  async ack(bytes: Uint8Array) {
    if (!this.conn) throw new Error('No link.');
    await this.conn.write(CAMERA.ack, bytes);
  }

  hurry(fast: boolean) {
    if (fast === this.fast || !this.conn) return;
    this.fast = fast;
    this.conn.device
      .requestConnectionPriority(fast ? ConnectionPriority.High : ConnectionPriority.Balanced)
      .catch(() => {});
  }

  async start() {
    if (this.running) return;
    this.running = true;
    this.target = loadPrefs().camera;

    if ((await requestBlePermissions()) !== 'granted') {
      this.running = false;
      this.set({ status: 'no-permission' });
      return;
    }
    if (!this.running) return;

    this.appState = AppState.addEventListener('change', (st) => {
      if (st === 'active' && this.waiting) {
        this.cancelWait();
        this.seek();
      }
    });
    this.powerSub = manager.onStateChange((power) => {
      if (power === 'PoweredOn') {
        if (this.s.status === 'bluetooth-off' || this.s.status === 'stopped') this.seek();
      } else if (power === 'PoweredOff' || power === 'Unauthorized') {
        this.dropConnection();
        this.stopScanning();
        this.clearTimers();
        this.set({
          status: power === 'PoweredOff' ? 'bluetooth-off' : 'no-permission',
          rssi: null,
          hasSettings: false,
          hasStills: false,
        });
      }
    }, true);
  }

  stop() {
    this.running = false;
    this.appState?.remove();
    this.appState = null;
    this.cancelWait();
    this.powerSub?.remove();
    this.powerSub = null;
    this.stopScanning();
    this.clearTimers();
    this.dropConnection();
    this.set({ ...IDLE });
  }

  choose(hit: ScanHit) {
    this.cancelWait();
    this.remember(hit);
    this.dropConnection();
    this.clearTimers();
    this.attempts = 0;
    void this.connectTo(hit);
  }

  forget() {
    savePrefs({ camera: null });
    this.target = null;
    this.cancelWait();
    this.dropConnection();
    this.stopScanning();
    this.clearTimers();
    this.set({ camera: null, rssi: null, hasSettings: false, hasStills: false });
    this.seek();
  }

  private seek() {
    if (!this.running || this.conn || this.stopScan || this.waiting) return;

    if (this.target && AppState.currentState !== 'active') {
      this.set({ status: 'reconnecting', camera: this.target });
      void this.connectTo({ ...this.target, rssi: null }, true);
      return;
    }

    if (this.target == null) {
      this.set({ status: 'scanning', hits: [], error: null });
    } else {
      if (this.s.status !== 'reconnecting') this.set({ status: 'looking', camera: this.target });
      this.later(GRACE_MS, () => {
        if (this.s.status === 'looking' || this.s.status === 'reconnecting') {
          this.set({ status: 'not-found' });
        }
      });
    }

    this.stopScan = scan(
      (hit) => this.sighted(hit),
      (e) => {
        this.stopScanning();
        this.retry(e.message);
      },
    );
  }

  private sighted(hit: ScanHit) {
    if (this.s.status === 'connecting' || this.conn) return;
    if (this.target?.id === hit.id) {
      void this.connectTo(hit);
      return;
    }
    const old = this.s.hits.find((h) => h.id === hit.id);
    if (old && Math.abs((old.rssi ?? 0) - (hit.rssi ?? 0)) < 3) return;
    const hits = [...this.s.hits.filter((h) => h.id !== hit.id), hit];
    hits.sort((a, b) => (b.rssi ?? -999) - (a.rssi ?? -999));
    this.set({ hits });
  }

  private async connectTo(hit: ScanHit, wait = false) {
    this.stopScanning();
    this.clearTimers();
    if (wait) this.waiting = hit.id;
    else this.set({ status: 'connecting', camera: { id: hit.id, name: hit.name }, rssi: hit.rssi });

    let conn: Connection;
    let hasSettings: boolean;
    let hasStills: boolean;
    try {
      conn = await connect(hit.id, wait);
      hasSettings = await conn.has(CAMERA.settings);
      hasStills = (await conn.has(CAMERA.stills)) && (await conn.has(CAMERA.ack));
    } catch (e) {
      if (wait && this.waiting !== hit.id) return;
      this.waiting = null;
      if (this.running) this.retry(e instanceof Error ? e.message : String(e));
      return;
    }
    if (wait) {
      const current = this.waiting === hit.id;
      this.waiting = null;
      if (!current) {
        conn.disconnect().catch(() => {});
        return;
      }
    }
    if (!this.running) {
      conn.disconnect().catch(() => {});
      return;
    }

    this.conn = conn;
    this.connectedAt = Date.now();
    this.remember(hit);
    this.connSubs.push(conn.onDisconnect(() => this.dropped()));
    if (hasSettings) {
      this.connSubs.push(conn.subscribe(CAMERA.settings, (bytes) => this.reader.push(bytes)));
    }
    if (hasStills) {
      this.connSubs.push(conn.subscribe(CAMERA.stills, (bytes) => this.stillPackets.emit(bytes)));
    }
    this.rssiTimer = setInterval(() => {
      conn.readRssi().then(
        (rssi) => this.conn === conn && this.set({ rssi }),
        () => {},
      );
    }, RSSI_MS);
    this.set({ status: 'connected', hasSettings, hasStills, hits: [], error: null });
  }

  private dropped() {
    this.dropConnection(false);
    if (!this.running) return;
    if (Date.now() - this.connectedAt > STABLE_MS) this.attempts = 0;
    this.set({ status: 'reconnecting', rssi: null, hasSettings: false, hasStills: false });
    this.retry(null);
  }

  private retry(error: string | null) {
    const wait = BACKOFF_MS[Math.min(this.attempts, BACKOFF_MS.length - 1)];
    this.attempts++;
    if (this.s.status !== 'reconnecting' && this.target) this.set({ status: 'reconnecting' });
    this.set({ error });
    this.later(wait, () => this.seek());
  }

  private remember(hit: ScanHit) {
    this.target = { id: hit.id, name: hit.name };
    savePrefs({ camera: this.target });
  }

  private dropConnection(close = true) {
    for (const sub of this.connSubs) sub.remove();
    this.connSubs = [];
    if (this.rssiTimer) clearInterval(this.rssiTimer);
    this.rssiTimer = null;
    const conn = this.conn;
    this.conn = null;
    this.fast = false;
    this.reader = new Reader((m) => this.messages.emit(m));
    if (close) conn?.disconnect().catch(() => {});
  }

  private cancelWait() {
    const id = this.waiting;
    this.waiting = null;
    if (id) manager.cancelDeviceConnection(id).catch(() => {});
  }

  private stopScanning() {
    this.stopScan?.();
    this.stopScan = null;
  }

  private later(ms: number, f: () => void) {
    const t = setTimeout(() => {
      this.timers.delete(t);
      f();
    }, ms);
    this.timers.add(t);
  }

  private clearTimers() {
    for (const t of this.timers) clearTimeout(t);
    this.timers.clear();
  }

  private set(patch: Partial<LinkState>) {
    this.s = { ...this.s, ...patch };
    this.changes.emit(this.s);
  }
}
