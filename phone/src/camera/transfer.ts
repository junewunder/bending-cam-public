import { utf8Decode } from '../ble/utf8';

const HEADER = 0xffffffff;
export const SKIP = 0xffffffff;
export const ACK_EVERY = 4;

export type Header = {
  fid: number;
  size: number;
  queued: number;
  name: string;
};

export function parseHeader(p: Uint8Array): Header | null {
  if (p.length < 12) return null;
  const v = new DataView(p.buffer, p.byteOffset, p.byteLength);
  if (v.getUint32(0, true) !== HEADER) return null;
  return {
    fid: v.getUint16(4, true),
    size: v.getUint32(6, true),
    queued: v.getUint16(10, true),
    name: utf8Decode(p.subarray(12)),
  };
}

export function ack(fid: number, offset: number): Uint8Array {
  const out = new Uint8Array(6);
  const v = new DataView(out.buffer);
  v.setUint16(0, fid, true);
  v.setUint32(2, offset, true);
  return out;
}

export type ReceiverEvents = {
  ack(bytes: Uint8Array): void;
  header(h: Header, taken: boolean): void;
  progress(got: number, size: number): void;
  file(h: Header, bytes: Uint8Array): void;
};

export class Receiver {
  private cur: { h: Header; buf: Uint8Array; exp: number; n: number } | null = null;
  private done: { fid: number; size: number } | null = null;

  constructor(
    private ev: ReceiverEvents,
    private wants: (h: Header) => boolean,
  ) {}

  push(p: Uint8Array) {
    if (p.length < 4) return;
    const h = parseHeader(p);
    if (h) return this.started(h);

    const cur = this.cur;
    if (!cur) {
      if (this.done) this.ev.ack(ack(this.done.fid, this.done.size));
      return;
    }
    const off = new DataView(p.buffer, p.byteOffset, 4).getUint32(0, true);
    if (off !== cur.exp) {
      this.ev.ack(ack(cur.h.fid, cur.exp));
      return;
    }
    const body = p.subarray(4, 4 + Math.min(p.length - 4, cur.h.size - off));
    cur.buf.set(body, off);
    cur.exp += body.length;
    cur.n++;
    this.ev.progress(cur.exp, cur.h.size);

    if (cur.exp >= cur.h.size) {
      this.ev.ack(ack(cur.h.fid, cur.exp));
      this.done = { fid: cur.h.fid, size: cur.h.size };
      this.cur = null;
      this.ev.file(cur.h, cur.buf);
    } else if (cur.n % ACK_EVERY === 0) {
      this.ev.ack(ack(cur.h.fid, cur.exp));
    }
  }

  reset() {
    this.cur = null;
    this.done = null;
  }

  private started(h: Header) {
    this.cur = null;
    const taken = this.wants(h);
    this.ev.header(h, taken);
    if (!taken) {
      this.ev.ack(ack(h.fid, SKIP));
      return;
    }
    this.cur = { h, buf: new Uint8Array(h.size), exp: 0, n: 0 };
    this.ev.ack(ack(h.fid, 0));
    if (h.size === 0) this.push(new Uint8Array(4));
  }
}

const WRITE_GIVE_UP_MS = 1000;

export class AckWriter {
  private busy = false;
  private next: Uint8Array | null = null;

  constructor(private write: (bytes: Uint8Array) => Promise<void>) {}

  send(bytes: Uint8Array) {
    this.next = bytes;
    if (!this.busy) void this.flush();
  }

  private async flush() {
    this.busy = true;
    while (this.next) {
      const b = this.next;
      this.next = null;
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        await Promise.race([
          this.write(b),
          new Promise((resolve) => (timer = setTimeout(resolve, WRITE_GIVE_UP_MS))),
        ]);
      } catch {
      } finally {
        clearTimeout(timer);
      }
    }
    this.busy = false;
  }
}
