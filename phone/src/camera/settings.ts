import { Emitter, type Link, type LinkState } from './link';
import { type Message, PROTO, type Setting, type Value } from './protocol';

export type Phase =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'offline'
  | 'unsupported'
  | 'wrong-proto'
  | 'failed';

export type Pending = { v?: Value; since: number };

export type SettingsState = {
  phase: Phase;
  rows: Setting[];
  values: Record<string, Value>;
  pending: Record<string, Pending>;
  notes: Record<string, string>;
  live: Record<string, Value>;
  proto: number | null;
  error: string | null;
};

const ECHO_MS = 3000;
const LOAD_MS = 5000;
const LOAD_TRIES = 3;
const NOTE_MS = 4000;

const EMPTY: SettingsState = {
  phase: 'idle',
  rows: [],
  values: {},
  pending: {},
  notes: {},
  live: {},
  proto: null,
  error: null,
};

export class Settings {
  private s = EMPTY;
  private changes = new Emitter<SettingsState>();
  private incoming: Setting[] | null = null;
  private tries = 0;
  private loadTimer: ReturnType<typeof setTimeout> | null = null;
  private echoTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private noteTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private unsubs: (() => void)[] = [];

  constructor(private link: Link) {}

  start() {
    this.unsubs = [
      this.link.watch((ls) => this.linkChanged(ls)),
      this.link.onMessage((m) => this.received(m)),
    ];
    this.linkChanged(this.link.state());
  }

  stop() {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
    this.clearTimers();
  }

  state() {
    return this.s;
  }

  watch(l: (s: SettingsState) => void) {
    return this.changes.add(l);
  }

  load() {
    this.tries = 0;
    this.requestDump();
  }

  change(k: string, v: Value) {
    if (this.s.phase !== 'ready') return;
    this.await(k, v);
    this.link.send({ k, v }).catch((e) => this.failed(k, e));
  }

  act(k: string) {
    if (this.s.phase !== 'ready') return;
    this.await(k, undefined);
    this.link.send({ k }).catch((e) => this.failed(k, e));
  }

  resetAll() {
    if (this.s.phase !== 'ready') return;
    for (const row of this.s.rows) if (row.kind !== 'action') this.await(row.k, undefined);
    this.link.send({ reset: 'all' }).catch((e) => {
      for (const row of this.s.rows) this.failed(row.k, e);
    });
  }

  private linkChanged(ls: LinkState) {
    if (ls.status === 'connected') {
      if (!ls.hasSettings) this.set({ phase: 'unsupported' });
      else if (this.s.phase !== 'loading' && this.s.phase !== 'ready') this.load();
      return;
    }
    this.clearTimers();
    this.incoming = null;
    this.set({
      phase: this.s.rows.length > 0 ? 'offline' : 'idle',
      pending: {},
      notes: {},
      live: {},
    });
  }

  private requestDump() {
    this.tries++;
    this.incoming = null;
    this.set({ phase: 'loading', error: null });
    if (this.loadTimer) clearTimeout(this.loadTimer);
    this.loadTimer = setTimeout(() => this.dumpFailed('The camera sent no settings.'), LOAD_MS);
    this.link.send({ get: 'all' }).catch((e) => this.dumpFailed(String(e?.message ?? e)));
  }

  private dumpFailed(error: string) {
    if (this.loadTimer) clearTimeout(this.loadTimer);
    this.loadTimer = null;
    if (this.link.state().status !== 'connected') return;
    if (this.tries < LOAD_TRIES) this.requestDump();
    else this.set({ phase: 'failed', error });
  }

  private received(m: Message) {
    switch (m.type) {
      case 'proto':
        if (m.proto !== PROTO) {
          if (this.loadTimer) clearTimeout(this.loadTimer);
          this.set({ phase: 'wrong-proto', proto: m.proto });
          return;
        }
        this.incoming = [];
        this.set({ proto: m.proto });
        return;
      case 'setting':
        this.incoming?.push(m.setting);
        return;
      case 'end': {
        const rows = this.incoming;
        if (rows == null || this.s.phase !== 'loading') return;
        if (rows.length !== m.count) {
          this.dumpFailed(`Got ${rows.length} of the camera's ${m.count} settings.`);
          return;
        }
        if (this.loadTimer) clearTimeout(this.loadTimer);
        this.loadTimer = null;
        this.incoming = null;
        const values: Record<string, Value> = {};
        for (const r of rows) if (r.kind !== 'action') values[r.k] = r.v;
        this.set({ phase: 'ready', rows, values, pending: {}, notes: {}, error: null });
        return;
      }
      case 'live':
        this.set({ live: { ...this.s.live, [m.k]: m.v } });
        return;
      case 'echo':
        this.echoed(m.k, m.v, m.err);
        return;
    }
  }

  private echoed(k: string, v: Value | undefined, err: string | undefined) {
    const asked = this.s.pending[k];
    const timer = this.echoTimers.get(k);
    if (timer) clearTimeout(timer);
    this.echoTimers.delete(k);

    const pending = { ...this.s.pending };
    delete pending[k];
    const values = v === undefined ? this.s.values : { ...this.s.values, [k]: v };
    this.set({ pending, values });

    const row = this.s.rows.find((r) => r.k === k);
    if (err) this.note(k, err);
    else if (row?.kind === 'action' && asked) this.note(k, 'done');
    else if (asked?.v !== undefined && v !== undefined && v !== asked.v) {
      this.note(k, `camera kept ${show(row, v)}`);
    }
  }

  private await(k: string, v: Value | undefined) {
    const old = this.echoTimers.get(k);
    if (old) clearTimeout(old);
    this.echoTimers.set(
      k,
      setTimeout(() => {
        this.echoTimers.delete(k);
        const pending = { ...this.s.pending };
        delete pending[k];
        this.set({ pending });
        this.note(k, 'no answer');
      }, ECHO_MS),
    );
    this.set({ pending: { ...this.s.pending, [k]: { v, since: Date.now() } } });
  }

  private failed(k: string, e: unknown) {
    const timer = this.echoTimers.get(k);
    if (timer) clearTimeout(timer);
    this.echoTimers.delete(k);
    const pending = { ...this.s.pending };
    delete pending[k];
    this.set({ pending });
    this.note(k, e instanceof Error ? e.message : String(e));
  }

  private note(k: string, text: string) {
    const old = this.noteTimers.get(k);
    if (old) clearTimeout(old);
    this.noteTimers.set(
      k,
      setTimeout(() => {
        this.noteTimers.delete(k);
        const notes = { ...this.s.notes };
        delete notes[k];
        this.set({ notes });
      }, NOTE_MS),
    );
    this.set({ notes: { ...this.s.notes, [k]: text } });
  }

  private clearTimers() {
    if (this.loadTimer) clearTimeout(this.loadTimer);
    this.loadTimer = null;
    for (const t of this.echoTimers.values()) clearTimeout(t);
    for (const t of this.noteTimers.values()) clearTimeout(t);
    this.echoTimers.clear();
    this.noteTimers.clear();
  }

  private set(patch: Partial<SettingsState>) {
    this.s = { ...this.s, ...patch };
    this.changes.emit(this.s);
  }
}

export function show(row: Setting | undefined, v: Value): string {
  if (row?.kind === 'enum' && typeof v === 'number') return row.opts[v] ?? String(v);
  if (typeof v === 'boolean') return v ? 'on' : 'off';
  return String(v);
}

export function requires(row: Setting, rows: Setting[], values: Record<string, Value>): string | null {
  for (const [k, allowed] of Object.entries(row.needs ?? {})) {
    const other = rows.find((r) => r.k === k);
    const v = values[k];
    if (!other || v === undefined || allowed.includes(v)) continue;
    return `requires ${other.label} to be ${allowed.map((a) => show(other, a)).join(' or ')}`;
  }
  return null;
}
