import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react';
import { AppState, Linking } from 'react-native';

import { requestBlePermissions } from '../ble/client';

import { loadPrefs, savePrefs } from '../store';
import { BleLink } from './ble';
import { FakeCamera } from './fake';
import type { Link, LinkState } from './link';
import { Settings, type SettingsState } from './settings';
import { KeepAlive } from './keepAlive';
import { Review, type ReviewState } from './review';
import { Stills, type StillsState } from './stills';
import { StillsNotice } from './stillsNotice';

type Camera = {
  link: Link;
  settings: Settings;
  stills: Stills;
  review: Review;
  keepAlive: KeepAlive;
  notice: StillsNotice;
  fake: boolean;
  setFake(fake: boolean): void;
  allow(): Promise<void>;
};

const Context = createContext<Camera | null>(null);

function open(fake: boolean) {
  const link: Link = fake ? new FakeCamera() : new BleLink();
  const stills = new Stills(link);
  return {
    link,
    settings: new Settings(link),
    stills,
    review: new Review(link, stills),
    keepAlive: new KeepAlive(link, stills),
    notice: new StillsNotice(stills),
  };
}

export function CameraProvider({ children }: { children: ReactNode }) {
  const [fake, setFakeState] = useState(() => loadPrefs().fake);
  const pair = useMemo(() => open(fake), [fake]);

  useEffect(() => {
    pair.settings.start();
    pair.stills.start();
    pair.review.start();
    pair.notice.start();
    pair.link.start();
    pair.keepAlive.start();
    const active = AppState.addEventListener('change', (st) => {
      if (st !== 'active') return;
      pair.keepAlive.start();
      if (pair.link.state().status === 'no-permission') pair.link.start();
    });
    return () => {
      active.remove();
      pair.keepAlive.stop();
      pair.notice.stop();
      pair.settings.stop();
      pair.stills.stop();
      pair.review.stop();
      pair.link.stop();
    };
  }, [pair]);

  const setFake = useCallback((next: boolean) => {
    savePrefs({ fake: next });
    setFakeState(next);
  }, []);

  const allow = useCallback(async () => {
    if ((await requestBlePermissions()) === 'blocked') await Linking.openSettings();
    else pair.link.start();
  }, [pair]);

  const value = useMemo(() => ({ ...pair, fake, setFake, allow }), [pair, fake, setFake, allow]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useCamera(): Camera {
  const cam = useContext(Context);
  if (!cam) throw new Error('useCamera outside CameraProvider');
  return cam;
}

export function useLink(): LinkState {
  const { link } = useCamera();
  return useSyncExternalStore(
    (l) => link.watch(l),
    () => link.state(),
  );
}

export function useSettings(): SettingsState {
  const { settings } = useCamera();
  return useSyncExternalStore(
    (l) => settings.watch(l),
    () => settings.state(),
  );
}

export function useStills(): StillsState {
  const { stills } = useCamera();
  return useSyncExternalStore(
    (l) => stills.watch(l),
    () => stills.state(),
  );
}

export function useReview(): ReviewState {
  const { review } = useCamera();
  return useSyncExternalStore(
    (l) => review.watch(l),
    () => review.state(),
  );
}

export function useKeepAliveError(): string | null {
  const { keepAlive } = useCamera();
  return useSyncExternalStore(
    (l) => keepAlive.watch(l),
    () => keepAlive.state(),
  );
}
