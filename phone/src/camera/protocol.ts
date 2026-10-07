import { utf8Decode, utf8Encode } from '../ble/utf8';

export const PROTO = 1;

export type When = 'live' | 'next shot';

export type Needs = Record<string, Value[]>;

type Common = { k: string; label: string; when?: When; group?: string; needs?: Needs };

export type Setting =
  | (Common & { kind: 'enum'; opts: string[]; v: number })
  | (Common & { kind: 'int'; min: number; max: number; step?: number; v: number })
  | (Common & { kind: 'bool'; v: boolean })
  | (Common & { kind: 'action'; confirm?: boolean });

export type Value = number | boolean;

export type Request =
  | { get: 'all' }
  | { k: string; v: Value }
  | { k: string }
  | { reset: 'all' }
  | { review: 'enter' | 'exit' }
  | { review: 'next' | 'prev'; by?: number }
  | { review: 'send'; files: string[] };

export type Shot = {
  shot: string;
  i: number;
  n: number;
  files: string[];
};

export type Message =
  | { type: 'proto'; proto: number }
  | { type: 'setting'; setting: Setting }
  | { type: 'end'; count: number }
  | { type: 'echo'; k: string; v?: Value; err?: string }
  | { type: 'live'; k: string; v: Value }
  | { type: 'review'; shot: Shot | null; queued?: string[]; why?: string; err?: string }
  | { type: 'other'; raw: unknown };

const KINDS = new Set(['enum', 'int', 'bool', 'action']);

export function parse(raw: unknown): Message {
  if (typeof raw !== 'object' || raw == null) return { type: 'other', raw };
  const o = raw as Record<string, unknown>;

  if (typeof o.proto === 'number') return { type: 'proto', proto: o.proto };
  if (typeof o.end === 'number') return { type: 'end', count: o.end };
  if ('review' in o) return parseReview(o);
  if (typeof o.k !== 'string') return { type: 'other', raw };

  if (typeof o.kind === 'string' && KINDS.has(o.kind)) {
    const s = { ...o, label: typeof o.label === 'string' ? o.label : o.k } as Setting;
    if (s.kind === 'bool') s.v = Boolean(o.v);
    if (s.kind === 'enum' && !Array.isArray(s.opts)) return { type: 'other', raw };
    if (s.needs !== undefined && !validNeeds(s.needs)) delete s.needs;
    return { type: 'setting', setting: s };
  }

  if ('live' in o) {
    const v = o.live;
    return typeof v === 'number' || typeof v === 'boolean' ? { type: 'live', k: o.k, v } : { type: 'other', raw };
  }

  return {
    type: 'echo',
    k: o.k,
    v: typeof o.v === 'number' || typeof o.v === 'boolean' ? o.v : undefined,
    err: typeof o.err === 'string' ? o.err : undefined,
  };
}

function parseReview(o: Record<string, unknown>): Message {
  const r = o.review as Record<string, unknown> | null;
  const strings = (x: unknown) => (Array.isArray(x) ? x.filter((f): f is string => typeof f === 'string') : undefined);
  let shot: Shot | null = null;
  if (r != null) {
    if (typeof r !== 'object' || typeof r.shot !== 'string') return { type: 'other', raw: o };
    shot = { shot: r.shot, i: Number(r.i) || 0, n: Number(r.n) || 0, files: strings(r.files) ?? [] };
  }
  return {
    type: 'review',
    shot,
    queued: strings(o.queued),
    why: typeof o.why === 'string' ? o.why : undefined,
    err: typeof o.err === 'string' ? o.err : undefined,
  };
}

function validNeeds(n: unknown): n is Needs {
  if (typeof n !== 'object' || n == null || Array.isArray(n)) return false;
  return Object.values(n).every(
    (vs) => Array.isArray(vs) && vs.every((v) => typeof v === 'number' || typeof v === 'boolean'),
  );
}

export function encode(req: Request): Uint8Array {
  return utf8Encode(JSON.stringify(req) + '\n');
}

export class Reader {
  private buf = new Uint8Array(0);

  constructor(private onMessage: (m: Message) => void) {}

  push(bytes: Uint8Array) {
    const joined = new Uint8Array(this.buf.length + bytes.length);
    joined.set(this.buf);
    joined.set(bytes, this.buf.length);

    let start = 0;
    for (let nl = joined.indexOf(10); nl >= 0; nl = joined.indexOf(10, start)) {
      this.take(joined.subarray(start, nl));
      start = nl + 1;
    }
    this.buf = joined.slice(start);

    if (this.buf.length > 0 && this.take(this.buf)) this.buf = new Uint8Array(0);
    else if (this.buf.length > 1024) this.buf = new Uint8Array(0);
  }

  private take(line: Uint8Array): boolean {
    const text = utf8Decode(line).trim();
    if (text === '') return true;
    try {
      this.onMessage(parse(JSON.parse(text)));
      return true;
    } catch {
      return false;
    }
  }
}
