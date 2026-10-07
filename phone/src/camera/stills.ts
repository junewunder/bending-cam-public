import StillsNative from '../../modules/stills';
import { loadPrefs, savePrefs } from '../store';
import { Emitter, type Link, type LinkState } from './link';
import { AckWriter, type Header, Receiver } from './transfer';

export type Mode = 'none' | 'screens' | 'all';

export type Arriving = {
  name: string;
  size: number;
  got: number;
  kbps: number | null;
  queued: number;
};

export type Received = {
  name: string;
  size: number;
  status: 'skipped' | 'saved' | 'converting' | 'done' | 'failed';
  seconds?: number;
  error?: string;
};

export type StillsState = {
  available: boolean;
  mode: Mode;
  arriving: Arriving | null;
  queued: number;
  recent: Received[];
  have: ReadonlySet<string>;
  asked: ReadonlySet<string>;
};

const JPEG_QUALITY = 90;
const ALBUM = 'bendcam';
const RECENT = 30;
const EMIT_MS = 250;

export class Stills {
  private s: StillsState;
  private changes = new Emitter<StillsState>();
  private files = new Emitter<Received>();
  private receiver: Receiver;
  private acks: AckWriter;
  private unsubs: (() => void)[] = [];
  private started = 0;
  private lastEmit = 0;
  private conversions: Promise<void> = Promise.resolve();
  private dir: string | null = null;

  constructor(private link: Link) {
    this.s = {
      available: false,
      mode: loadPrefs().stills,
      arriving: null,
      queued: 0,
      recent: [],
      have: new Set(),
      asked: new Set(),
    };
    this.acks = new AckWriter((b) => this.link.ack(b));
    this.receiver = new Receiver(
      {
        ack: (b) => this.acks.send(b),
        header: (h, taken) => this.header(h, taken),
        progress: (got) => this.progress(got),
        file: (h, bytes) => this.file(h, bytes),
      },
      (h) =>
        this.s.mode === 'all' ||
        (this.s.mode === 'screens' && h.name.includes('_screen')) ||
        this.s.asked.has(h.name),
    );
  }

  start() {
    this.unsubs = [
      this.link.watch((ls) => this.linkChanged(ls)),
      this.link.onStillPacket((p) => this.receiver.push(p)),
    ];
    this.linkChanged(this.link.state());
    try {
      const names = StillsNative.list(this.folder()).filter((n) => /\.bmp$/i.test(n));
      this.set({ have: new Set([...this.s.have, ...names]) });
    } catch {
    }
  }

  stop() {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
    this.receiver.reset();
  }

  ask(names: string[]) {
    if (names.length === 0) return;
    this.set({ asked: new Set([...this.s.asked, ...names]) });
  }

  unask(names: string[]) {
    const asked = new Set(this.s.asked);
    for (const n of names) asked.delete(n);
    this.set({ asked });
  }

  state() {
    return this.s;
  }

  watch(l: (s: StillsState) => void) {
    return this.changes.add(l);
  }

  onFile(l: (r: Received) => void) {
    return this.files.add(l);
  }

  setMode(mode: Mode) {
    savePrefs({ stills: mode });
    this.set({ mode });
  }

  private linkChanged(ls: LinkState) {
    const available = ls.status === 'connected' && ls.hasStills;
    if (available === this.s.available) return;
    if (!available) {
      this.receiver.reset();
      this.acks = new AckWriter((b) => this.link.ack(b));
      this.set({ available, arriving: null });
      return;
    }
    this.set({ available });
  }

  private header(h: Header, taken: boolean) {
    if (!taken) {
      this.remember({ name: h.name, size: h.size, status: 'skipped' });
      this.set({ queued: h.queued, arriving: null });
      if (h.queued === 0) this.link.hurry(false);
      return;
    }
    this.started = Date.now();
    this.set({ arriving: { name: h.name, size: h.size, got: 0, kbps: null, queued: h.queued }, queued: h.queued });
    this.link.hurry(true);
  }

  private progress(got: number) {
    const a = this.s.arriving;
    const now = Date.now();
    if (!a || now - this.lastEmit < EMIT_MS) return;
    this.lastEmit = now;
    const secs = (now - this.started) / 1000;
    const next = { ...a, got, kbps: secs > 1 ? got / 1024 / secs : null };
    this.set({ arriving: next });
  }

  private file(h: Header, bytes: Uint8Array) {
    const seconds = (Date.now() - this.started) / 1000;
    const asked = new Set(this.s.asked);
    asked.delete(h.name);
    this.set({ arriving: null, asked });
    try {
      const bmp = this.save(h.name, bytes);
      this.set({ have: new Set(this.s.have).add(h.name) });
      this.remember({ name: h.name, size: h.size, status: 'saved', seconds });
      this.convert(h.name, bmp);
    } catch (e) {
      this.remember({ name: h.name, size: h.size, status: 'failed', seconds, error: message(e) });
    }
    if (h.queued === 0) this.link.hurry(false);
  }

  private save(name: string, bytes: Uint8Array): string {
    const uri = `${this.folder()}/${encodeURIComponent(name)}`;
    StillsNative.save(uri, bytes);
    return uri;
  }

  private folder(): string {
    this.dir ??= StillsNative.dir().replace(/\/$/, '');
    return this.dir;
  }

  private convert(name: string, bmp: string) {
    this.conversions = this.conversions.then(async () => {
      this.update(name, { status: 'converting' });
      try {
        const jpg = bmp.replace(/\.bmp$/i, '') + '.jpg';
        await StillsNative.toJpeg(bmp, jpg, JPEG_QUALITY);
        await StillsNative.toGallery(jpg, ALBUM);
        this.update(name, { status: 'done' });
      } catch (e) {
        this.update(name, { status: 'failed', error: message(e) });
      }
    });
  }

  private remember(r: Received) {
    const recent = [r, ...this.s.recent.filter((x) => x.name !== r.name)].slice(0, RECENT);
    this.set({ recent });
    this.files.emit(r);
  }

  private update(name: string, patch: Partial<Received>) {
    this.set({ recent: this.s.recent.map((r) => (r.name === name ? { ...r, ...patch } : r)) });
  }

  private set(patch: Partial<StillsState>) {
    this.s = { ...this.s, ...patch };
    this.changes.emit(this.s);
  }
}

export function describe(a: Arriving): string {
  const pct = a.size ? Math.floor((a.got * 100) / a.size) : 100;
  const rate = a.kbps != null ? ` · ${a.kbps.toFixed(1)} KB/s` : '';
  return `${pct}% of ${Math.round(a.size / 1024)} KB${rate} · ${a.queued} more queued`;
}

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
