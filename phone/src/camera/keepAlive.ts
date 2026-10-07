import { AppState, PermissionsAndroid, Platform } from 'react-native';

import ForegroundService from '../../modules/foreground-service';
import { Emitter, type Link, type LinkStatus } from './link';
import type { Stills } from './stills';

const NOTIFY_MS = 1000;

const WORDS: Record<LinkStatus, string> = {
  scanning: 'Pick a camera in the app',
  looking: 'Looking for the camera',
  'not-found': 'Looking for the camera',
  connecting: 'Connecting',
  connected: 'Connected',
  reconnecting: 'Reconnecting',
  'bluetooth-off': 'Bluetooth is off',
  'no-permission': 'No Bluetooth permission',
  stopped: 'Off',
};

export class KeepAlive {
  private error: string | null = null;
  private changes = new Emitter<string | null>();
  private unsubs: (() => void)[] = [];
  private shown = '';
  private lastNotify = 0;
  private trailing: ReturnType<typeof setTimeout> | null = null;
  private askedNotify = false;

  constructor(
    private link: Link,
    private stills: Stills,
  ) {}

  start() {
    if (Platform.OS !== 'android') return;
    if (this.unsubs.length === 0) {
      this.unsubs = [this.link.watch(() => this.notify()), this.stills.watch(() => this.notify())];
    }
    this.askNotify();
    const [title, body] = this.text();
    ForegroundService.start(title, body).then(
      () => this.setError(null),
      (e) => this.setError(e instanceof Error ? e.message : String(e)),
    );
    this.shown = title + body;
  }

  stop() {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
    if (this.trailing) clearTimeout(this.trailing);
    this.trailing = null;
    ForegroundService.stop().catch(() => {});
  }

  state() {
    return this.error;
  }

  watch(l: (e: string | null) => void) {
    return this.changes.add(l);
  }

  private notify() {
    this.askNotify();
    const [title, body] = this.text();
    if (title + body === this.shown) return;
    const wait = this.lastNotify + NOTIFY_MS - Date.now();
    if (wait > 0) {
      this.trailing ??= setTimeout(() => {
        this.trailing = null;
        this.notify();
      }, wait);
      return;
    }
    this.lastNotify = Date.now();
    this.shown = title + body;
    ForegroundService.update(title, body).catch(() => {});
  }

  private askNotify() {
    const status = this.link.state().status;
    if (this.askedNotify || status === 'stopped' || status === 'no-permission') return;
    if (AppState.currentState !== 'active' || Number(Platform.Version) < 33) return;
    this.askedNotify = true;
    PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS).catch(() => {});
  }

  private text(): [string, string] {
    const ls = this.link.state();
    const st = this.stills.state();
    const name = ls.camera?.name ?? 'bendcam';
    const got = st.recent.filter((r) => r.status === 'done').length;
    return [`${name}: ${WORDS[ls.status].toLowerCase()}`, got ? `${got} ${got === 1 ? 'still' : 'stills'} to the gallery this session` : ''];
  }

  private setError(error: string | null) {
    if (error === this.error) return;
    this.error = error;
    this.changes.emit(error);
  }
}
