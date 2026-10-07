import { Platform } from 'react-native';

import ForegroundService from '../../modules/foreground-service';
import type { Arriving, Received, Stills, StillsState } from './stills';

const NOTIFY_MS = 1000;

export class StillsNotice {
  private unsubs: (() => void)[] = [];
  private taken = new Set<string>();
  private skipped = 0;
  private last: Arriving | null = null;
  private lastPost = 0;
  private trailing: ReturnType<typeof setTimeout> | null = null;
  private pending: [string, string, number, number, boolean] | null = null;

  constructor(private stills: Stills) {}

  start() {
    if (Platform.OS !== 'android') return;
    this.unsubs = [
      this.stills.watch((st) => this.changed(st)),
      this.stills.onFile((r) => {
        if (r.status === 'skipped') {
          if (this.taken.size) this.skipped++;
        } else this.taken.add(r.name);
      }),
    ];
  }

  stop() {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
    this.cancelTrailing();
    this.pending = null;
    ForegroundService.clearStills().catch(() => {});
  }

  private changed(st: StillsState) {
    const a = st.arriving;
    if (a) {
      this.taken.add(a.name);
      this.last = a;
      this.progress(a);
      return;
    }
    if (!this.taken.size) return;
    if (!st.available) {
      if (this.last) this.post(`Link lost during ${this.last.name}`, `Stopped at ${percent(this.last)}%. The camera sends it again when it reconnects.`, false);
      this.last = null;
      return;
    }
    this.last = null;
    const status = new Map(st.recent.map((r) => [r.name, r.status]));
    const busy = [...this.taken].filter((n) => {
      const s = status.get(n);
      return s ? s === 'saved' || s === 'converting' : st.available;
    });
    const queued = st.available && st.queued > 0;
    if (busy.length || queued) {
      const doing = busy.length ? `Saving ${busy[0]} to the gallery` : 'Waiting for the next one';
      this.post('Stills arriving', `${doing} · ${st.queued} more queued`, true);
      return;
    }
    if ([...this.taken].some((n) => !status.has(n))) return;
    this.summary(st.recent.filter((r) => this.taken.has(r.name)), st.available ? 0 : st.queued);
  }

  private progress(a: Arriving) {
    const left = a.kbps ? Math.round((a.size - a.got) / 1024 / a.kbps) : null;
    const body = [
      `${percent(a)}% of ${Math.round(a.size / 1024)} KB`,
      a.kbps != null && `${a.kbps.toFixed(1)} KB/s`,
      left != null && `${clock(left)} left`,
      `${a.queued} more queued`,
    ].filter(Boolean).join(' · ');
    this.post(`Receiving ${a.name}`, body, true, a.got, a.size);
  }

  private summary(mine: Received[], waiting: number) {
    const done = mine.filter((r) => r.status === 'done');
    const failed = mine.filter((r) => r.status === 'failed');
    const lines = [];
    if (done.length) lines.push(`In the bendcam album: ${names(done)}`);
    if (failed.length) lines.push(`Failed: ${failed.map((r) => `${r.name} (${r.error ?? 'unknown'})`).join(', ')}`);
    if (this.skipped) lines.push(`${this.skipped} left on the camera for a later connection`);
    if (waiting) lines.push(`Link lost with ${waiting} more queued; they come on the next connection`);
    const title = failed.length ? `${done.length} of ${mine.length} stills received` : `${plural(done.length, 'still')} received`;
    this.post(title, lines.join('\n'), false);
    this.taken.clear();
    this.skipped = 0;
  }

  private post(title: string, body: string, active: boolean, got = 0, size = 0) {
    this.pending = [title, body, got, size, active];
    const wait = this.lastPost + NOTIFY_MS - Date.now();
    if (wait > 0) {
      this.trailing ??= setTimeout(() => {
        this.trailing = null;
        this.flush();
      }, wait);
      return;
    }
    this.flush();
  }

  private flush() {
    const p = this.pending;
    if (!p) return;
    this.pending = null;
    this.lastPost = Date.now();
    ForegroundService.stills(...p).catch(() => {});
  }

  private cancelTrailing() {
    if (this.trailing) clearTimeout(this.trailing);
    this.trailing = null;
  }
}

function percent(a: Arriving) {
  return a.size ? Math.floor((a.got * 100) / a.size) : 100;
}

function clock(s: number) {
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

function names(rs: Received[]) {
  const shown = rs.slice(0, 4).map((r) => r.name.replace(/\.bmp$/i, ''));
  return shown.join(', ') + (rs.length > shown.length ? ` and ${rs.length - shown.length} more` : '');
}
