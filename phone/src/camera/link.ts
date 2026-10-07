import type { Message, Request } from './protocol';

export type LinkStatus =
  | 'scanning'
  | 'looking'
  | 'not-found'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'bluetooth-off'
  | 'no-permission'
  | 'stopped';

export type ScanHit = { id: string; name: string | null; rssi: number | null };

export type LinkState = {
  status: LinkStatus;
  camera: { id: string; name: string | null } | null;
  rssi: number | null;
  hits: ScanHit[];
  hasSettings: boolean;
  hasStills: boolean;
  fake: boolean;
  error: string | null;
};

export interface Link {
  state(): LinkState;
  watch(listener: (s: LinkState) => void): () => void;
  onMessage(listener: (m: Message) => void): () => void;
  send(req: Request): Promise<void>;
  onStillPacket(listener: (p: Uint8Array) => void): () => void;
  ack(bytes: Uint8Array): Promise<void>;
  hurry(fast: boolean): void;

  start(): void;
  stop(): void;
  choose(hit: ScanHit): void;
  forget(): void;
  simulateDrop?(): void;
  shoot?(): void;
}

export const IDLE: LinkState = {
  status: 'stopped',
  camera: null,
  rssi: null,
  hits: [],
  hasSettings: false,
  hasStills: false,
  fake: false,
  error: null,
};

export class Emitter<T> {
  private listeners = new Set<(v: T) => void>();

  add(l: (v: T) => void): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  emit(v: T) {
    for (const l of this.listeners) l(v);
  }
}
