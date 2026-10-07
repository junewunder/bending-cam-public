import { requireNativeModule } from 'expo';
import { AppRegistry } from 'react-native';

type ForegroundServiceModule = {
  start(title: string, body: string): Promise<void>;
  update(title: string, body: string): Promise<void>;
  stop(): Promise<void>;
  stills(title: string, body: string, got: number, size: number, active: boolean): Promise<void>;
  clearStills(): Promise<void>;
  isRunning(): Promise<boolean>;
};

AppRegistry.registerHeadlessTask('BendcamKeepAlive', () => () => new Promise<void>(() => {}));

export default requireNativeModule<ForegroundServiceModule>('ForegroundService');
