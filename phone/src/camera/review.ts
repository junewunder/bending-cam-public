import { Emitter, type Link, type LinkState } from './link';
import type { Message, Request, Shot } from './protocol';
import type { Stills } from './stills';

export type ReviewState = {
  phase: 'off' | 'opening' | 'on';
  shot: Shot | null;
  waiting: boolean;
  note: string | null;
};

const ANSWER_MS = 4000;

const WHY: Record<string, string | null> = {
  phone: null,
  shutter: 'The shutter was pressed: the camera is back on its preview.',
  idle: 'Review ended by itself after two minutes without a press.',
  'no card': 'No card in the camera.',
  'card failed': 'The card failed; the camera is back on its preview.',
  'no stills on the card': 'No stills on the card.',
};

const OFF: ReviewState = { phase: 'off', shot: null, waiting: false, note: null };

export class Review {
  private s = OFF;
  private changes = new Emitter<ReviewState>();
  private unsubs: (() => void)[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  private steps = 0;
  private asking: string[] = [];

  constructor(
    private link: Link,
    private stills: Stills,
  ) {}

  start() {
    this.unsubs = [
      this.link.watch((ls) => this.linkChanged(ls)),
      this.link.onMessage((m) => this.received(m)),
    ];
  }

  stop() {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
    this.clearTimer();
  }

  state() {
    return this.s;
  }

  watch(l: (s: ReviewState) => void) {
    return this.changes.add(l);
  }

  enter() {
    if (this.link.state().status !== 'connected') {
      this.set({ ...OFF, note: 'Not connected.' });
      return;
    }
    if (this.s.phase === 'off') this.set({ phase: 'opening', note: null });
    this.ask({ review: 'enter' });
  }

  exit() {
    this.steps = 0;
    this.clearTimer();
    if (this.s.phase === 'off') return;
    this.set(OFF);
    this.link.send({ review: 'exit' }).catch(() => {
    });
  }

  step(by: number) {
    if (this.s.phase !== 'on') return;
    if (this.s.waiting) {
      this.steps += by;
      return;
    }
    this.ask(by > 0 ? { review: 'next', by } : { review: 'prev', by: -by });
  }

  get(files: string[]) {
    if (this.s.phase !== 'on' || files.length === 0) return;
    this.stills.ask(files);
    this.asking = files;
    this.ask({ review: 'send', files });
  }

  private ask(req: Request) {
    this.set({ waiting: true, note: null });
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      this.steps = 0;
      if (this.s.phase === 'opening') {
        this.set({ ...OFF, note: 'No answer. Does this camera’s firmware have review mode?' });
      } else {
        this.set({ waiting: false, note: 'No answer from the camera.' });
      }
    }, ANSWER_MS);
    this.link.send(req).catch((e) => {
      this.clearTimer();
      this.stills.unask(this.asking);
      this.asking = [];
      this.steps = 0;
      const note = e instanceof Error ? e.message : String(e);
      this.set(this.s.phase === 'opening' ? { ...OFF, note } : { waiting: false, note });
    });
  }

  private received(m: Message) {
    if (m.type !== 'review') return;
    if (m.shot == null) {
      this.clearTimer();
      this.steps = 0;
      this.set({ ...OFF, note: m.err ?? (m.why !== undefined ? (WHY[m.why] ?? m.why) : null) });
      return;
    }
    if (this.s.phase === 'off') {
      this.link.send({ review: 'exit' }).catch(() => {});
      return;
    }
    const answer = this.s.waiting;
    if (answer) this.clearTimer();
    if (m.queued) {
      this.stills.unask(this.asking.filter((f) => !m.queued!.includes(f)));
      this.asking = [];
    }
    this.set({ phase: 'on', shot: m.shot, waiting: false, note: m.err ?? this.s.note });
    if (answer && this.steps !== 0) {
      const by = this.steps;
      this.steps = 0;
      this.step(by);
    }
  }

  private linkChanged(ls: LinkState) {
    if (ls.status === 'connected' || this.s.phase === 'off') return;
    this.clearTimer();
    this.steps = 0;
    this.set({ ...OFF, note: 'The link dropped, and the camera went back to its preview.' });
  }

  private clearTimer() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private set(patch: Partial<ReviewState>) {
    this.s = { ...this.s, ...patch };
    this.changes.emit(this.s);
  }
}
