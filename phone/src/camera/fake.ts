import { utf8Encode } from '../ble/utf8';
import { Emitter, IDLE, type Link, type LinkState, type ScanHit } from './link';
import { type Message, PROTO, type Request, type Setting, type Value, parse } from './protocol';
import { SKIP } from './transfer';

type Row = Setting & { def?: Value };

const TABLE: Row[] = [
  { k: 'exposure', label: 'Exposure', kind: 'enum', group: 'Exposure',
    opts: ['auto', 'lock', 'manual'], v: 0, def: 0, when: 'live' },
  { k: 'ev', label: 'Bias (auto), 1/3 stops', kind: 'int', group: 'Exposure',
    min: -8, max: 8, step: 1, v: 0, def: 0, when: 'live', needs: { exposure: [0] } },
  { k: 'exposure_value', label: 'Shutter (manual), 1/3 stops', kind: 'int', group: 'Exposure',
    min: 0, max: 30, v: 30, def: 30, when: 'live', needs: { exposure: [2] } },
  { k: 'iso', label: 'ISO (manual)', kind: 'int', group: 'Exposure',
    min: 100, max: 1550, step: 50, v: 400, def: 400, when: 'live', needs: { exposure: [2] } },
  { k: 'wb', label: 'White balance', kind: 'enum', group: 'White balance',
    opts: ['auto', 'lock', 'sun', 'cloud', 'office', 'home', 'manual'], v: 0, def: 0, when: 'live' },
  { k: 'wb_r', label: 'Red (manual), 1024 = 1x', kind: 'int', group: 'White balance',
    min: 256, max: 3072, step: 32, v: 1024, def: 1024, when: 'live', needs: { wb: [6] } },
  { k: 'bright', label: 'Preview brightness', kind: 'int', group: 'Picture',
    min: 0, max: 100, step: 5, v: 50, def: 50, when: 'live' },
  { k: 'shift', label: 'Byte shift', kind: 'int', group: 'Bends',
    min: 0, max: 7, step: 1, v: 0, def: 0, when: 'live' },
  { k: 'swap', label: 'Swap bytes', kind: 'bool', group: 'Bends', v: false, def: false, when: 'live' },
  { k: 'ghost', label: 'Ghost (never answers)', kind: 'bool', group: 'Bends',
    v: false, def: false, when: 'live' },
  { k: 'size', label: 'Still size', kind: 'enum', group: 'Stills',
    opts: ['QVGA', 'VGA', 'XGA', 'UXGA', 'QXGA'], v: 2, def: 2, when: 'next shot' },
  { k: 'screen', label: 'Save a screen copy', kind: 'bool', group: 'Stills',
    v: true, def: true, when: 'next shot' },
  { k: 'rebuild', label: 'Restart the sensor', kind: 'action', group: 'Camera', confirm: true },
  { k: 'flash', label: 'Blink the status art', kind: 'action', group: 'Camera' },
];

const HIT: ScanHit = { id: 'fake', name: 'bendcam (fake)', rssi: -52 };

const LINE_MS = 50;
const ECHO_MS = 250;
const DRAW_MS = 200;

export class FakeCamera implements Link {
  private s: LinkState = { ...IDLE, fake: true };
  private changes = new Emitter<LinkState>();
  private messages = new Emitter<Message>();
  private outbox = new FakeOutbox((p) => this.s.status === 'connected' && this.stillPackets.emit(p));
  private stillPackets = new Emitter<Uint8Array>();
  private table = TABLE.map((r) => ({ ...r }));
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private rssiTimer: ReturnType<typeof setInterval> | null = null;
  private reviewing: number | null = null;

  state() {
    return this.s;
  }

  watch(l: (s: LinkState) => void) {
    return this.changes.add(l);
  }

  onMessage(l: (m: Message) => void) {
    return this.messages.add(l);
  }

  onStillPacket(l: (p: Uint8Array) => void) {
    return this.stillPackets.add(l);
  }

  async ack(bytes: Uint8Array) {
    if (this.s.status !== 'connected') throw new Error('Not connected.');
    this.outbox.acked(bytes);
  }

  hurry() {}

  shoot() {
    this.outbox.shoot();
  }

  start() {
    this.set({ status: 'connecting', camera: HIT, hits: [HIT] });
    this.later(400, () => this.up());
    this.rssiTimer = setInterval(() => {
      if (this.s.status !== 'connected') return;
      this.set({ rssi: -48 - Math.round(Math.random() * 12) });
      const wander = (v: number, d: number) => v + d * Math.round((Math.random() - 0.5) * 4);
      this.echo({ k: 'exposure_value', live: wander(28, 1) });
      this.echo({ k: 'iso', live: wander(600, 50) });
      this.echo({ k: 'wb_r', live: wander(1248, 32) });
    }, 2000);
  }

  stop() {
    for (const t of this.timers) clearTimeout(t);
    this.timers.clear();
    this.outbox.stop();
    if (this.rssiTimer) clearInterval(this.rssiTimer);
    this.rssiTimer = null;
    this.set({ ...IDLE, fake: true });
  }

  choose() {}

  forget() {}

  simulateDrop() {
    if (this.s.status !== 'connected') return;
    this.reviewing = null;
    this.outbox.stop();
    this.set({ status: 'reconnecting', rssi: null, hasSettings: false, hasStills: false });
    this.later(3000, () => this.set({ status: 'connecting' }));
    this.later(3400, () => this.up());
  }

  private up() {
    this.set({ status: 'connected', hasSettings: true, hasStills: true, rssi: HIT.rssi });
    this.outbox.start();
  }

  async send(req: Request) {
    if (this.s.status !== 'connected') throw new Error('Not connected.');
    if ('get' in req) return this.dump();
    if ('reset' in req) {
      this.table.forEach((row, i) => {
        if (row.kind === 'action' || row.def === undefined) return;
        row.v = row.def;
        this.later(ECHO_MS + i * LINE_MS, () => this.echo({ k: row.k, v: row.def }));
      });
      return;
    }
    if ('review' in req) return this.review(req);

    const row = this.table.find((r) => r.k === req.k);
    if (!row) return this.later(ECHO_MS, () => this.echo({ k: req.k, err: 'no such setting' }));
    if (row.k === 'ghost') return;
    if (row.kind === 'action') return this.later(ECHO_MS * 3, () => this.echo({ k: row.k }));
    if (!('v' in req)) return;

    let v = req.v;
    if (row.kind === 'int' && typeof v === 'number') {
      v = Math.min(row.max, Math.max(row.min, v));
      if (row.k === 'ev') v = Math.min(v, 6);
    }
    if (row.kind === 'enum' && typeof v === 'number') {
      if (!(v >= 0 && v < row.opts.length) || row.opts[v] === 'QXGA') v = row.v;
    }
    if (row.kind === 'bool') v = Boolean(v);
    row.v = v as never;
    this.later(ECHO_MS, () => this.echo({ k: row.k, v }));
  }

  private review(req: Extract<Request, { review: string }>) {
    const n = this.outbox.shots();
    const files = (i: number) => {
      const stem = `FAKE_${String(i).padStart(4, '0')}`;
      return i % 3 === 0 ? [`${stem}_screen.bmp`] : [`${stem}_screen.bmp`, `${stem}.bmp`];
    };
    const line = (extra: object = {}) => {
      const i = this.reviewing!;
      return { review: { shot: `FAKE_${String(i).padStart(4, '0')}`, i, n, files: files(i) }, ...extra };
    };
    if (req.review === 'exit') {
      this.reviewing = null;
      return this.later(ECHO_MS, () => this.echo({ review: null, why: 'phone' }));
    }
    if (this.reviewing == null) {
      if (req.review !== 'enter') return this.later(ECHO_MS, () => this.echo({ review: null, err: 'not reviewing' }));
      this.reviewing = n;
    }
    const by = 'by' in req && req.by ? req.by : 1;
    if (req.review === 'next') this.reviewing = Math.min(n, this.reviewing + by);
    if (req.review === 'prev') this.reviewing = Math.max(1, this.reviewing - by);
    if (req.review === 'send') {
      const queued = files(this.reviewing).filter((f) => req.files.includes(f));
      this.outbox.request(queued);
      return this.later(ECHO_MS, () => this.echo(line({ queued })));
    }
    this.later(DRAW_MS, () => this.echo(line()));
  }

  private dump() {
    const lines: object[] = [{ proto: PROTO }, ...this.table.map(({ def, ...s }) => s)];
    lines.push({ end: this.table.length });
    lines.forEach((line, i) => this.later(LINE_MS * (i + 1), () => this.echo(line)));
  }

  private echo(raw: object) {
    if (this.s.status === 'connected') this.messages.emit(parse(raw));
  }

  private later(ms: number, f: () => void) {
    const t = setTimeout(() => {
      this.timers.delete(t);
      f();
    }, ms);
    this.timers.add(t);
  }

  private set(patch: Partial<LinkState>) {
    this.s = { ...this.s, ...patch };
    this.changes.emit(this.s);
  }
}

class FakeOutbox {
  private static WINDOW = 8;
  private static PAYLOAD = 249;
  private static PUMP_MS = 60;
  private static WAIT_MS = 250;

  private queue: { name: string; w: number; h: number; n: number }[] = [];
  private aside: typeof this.queue = [];
  private shot = 0;
  private fid = 0;
  private file: { bytes: Uint8Array; base: number; sent: number; t: number } | null = null;
  private ctl: { fid: number; off: number } | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(private notify: (p: Uint8Array) => void) {
    this.shoot();
  }

  shoot() {
    const n = ++this.shot;
    const stem = `FAKE_${String(n).padStart(4, '0')}`;
    this.queue.push({ name: `${stem}_screen.bmp`, w: 320, h: 240, n }, { name: `${stem}.bmp`, w: 1024, h: 768, n });
  }

  shots() {
    return this.shot;
  }

  request(names: string[]) {
    const busy = this.file ? this.queue[0]?.name : undefined;
    const add = names
      .filter((name) => name !== busy)
      .map((name) => {
        const n = Number(name.slice(5, 9));
        const screen = name.includes('_screen');
        return { name, w: screen ? 320 : 1024, h: screen ? 240 : 768, n };
      });
    const drop = (q: typeof this.queue) => q.filter((e) => !names.includes(e.name) || e.name === busy);
    this.queue = drop(this.queue);
    this.aside = drop(this.aside);
    this.queue.splice(this.file ? 1 : 0, 0, ...add);
  }

  acked(b: Uint8Array) {
    if (b.length !== 6) return;
    const v = new DataView(b.buffer, b.byteOffset, 6);
    this.ctl = { fid: v.getUint16(0, true), off: v.getUint32(2, true) };
  }

  start() {
    if (!this.timer) this.timer = setInterval(() => this.pump(), FakeOutbox.PUMP_MS);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.file = null;
    this.queue.unshift(...this.aside);
    this.aside = [];
  }

  private pump() {
    const now = Date.now();
    if (!this.file) {
      const next = this.queue[0];
      if (!next) return;
      this.fid = (this.fid + 1) & 0xffff;
      this.file = { bytes: fakeBmp(next.w, next.h, next.n), base: 0, sent: 0, t: now };
      this.header();
      return;
    }
    const f = this.file;
    const base = this.ctl?.fid === this.fid ? this.ctl.off : -1;
    if (base < 0) {
      if (now - f.t > FakeOutbox.WAIT_MS) this.header();
      return;
    }
    if (base === SKIP) {
      this.aside.push(this.queue.shift()!);
      this.file = null;
      return;
    }
    if (base >= f.bytes.length) {
      this.queue.shift();
      this.file = null;
      return;
    }
    if (base !== f.base) {
      f.base = base;
      f.t = now;
    } else if (now - f.t > FakeOutbox.WAIT_MS) {
      f.sent = base;
      f.t = now;
    }
    f.sent = Math.max(f.sent, base);
    const limit = Math.min(f.bytes.length, base + FakeOutbox.WINDOW * FakeOutbox.PAYLOAD);
    while (f.sent < limit) {
      const k = Math.min(FakeOutbox.PAYLOAD, limit - f.sent);
      const p = new Uint8Array(4 + k);
      new DataView(p.buffer).setUint32(0, f.sent, true);
      p.set(f.bytes.subarray(f.sent, f.sent + k), 4);
      if (Math.random() >= 0.02) this.notify(p);
      f.sent += k;
    }
  }

  private header() {
    const name = utf8Encode(this.queue[0].name);
    const p = new Uint8Array(12 + name.length);
    const v = new DataView(p.buffer);
    v.setUint32(0, 0xffffffff, true);
    v.setUint16(4, this.fid, true);
    v.setUint32(6, this.file!.bytes.length, true);
    v.setUint16(10, this.queue.length - 1, true);
    p.set(name, 12);
    this.file!.t = Date.now();
    this.notify(p);
  }
}

function fakeBmp(w: number, h: number, n: number): Uint8Array {
  const DATA = 512;
  const out = new Uint8Array(DATA + w * h * 2);
  const v = new DataView(out.buffer);
  out[0] = 0x42;
  out[1] = 0x4d;
  v.setUint32(2, out.length, true);
  v.setUint32(10, DATA, true);
  v.setUint32(14, 40, true);
  v.setInt32(18, w, true);
  v.setInt32(22, h, true);
  v.setUint16(26, 1, true);
  v.setUint16(28, 16, true);
  v.setUint32(30, 3, true);
  v.setUint32(34, w * h * 2, true);
  v.setUint32(54, 0xf800, true);
  v.setUint32(58, 0x07e0, true);
  v.setUint32(62, 0x001f, true);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const band = (((x + y + n * 37) >> 4) & 1) * 31;
      const r = (x * 31) / w;
      const b = (y * 31) / h;
      v.setUint16(DATA + (y * w + x) * 2, (r << 11) | (band * 2) << 5 | b, true);
    }
  }
  return out;
}
