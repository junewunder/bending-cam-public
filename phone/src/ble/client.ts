import { PermissionsAndroid, Platform } from 'react-native';
import { BleManager, type Device, type Subscription } from 'react-native-ble-plx';

import { CAMERA, type Endpoint } from '../config/camera';
import { base64ToBytes, bytesToBase64 } from './base64';

const ATT_HEADER_BYTES = 3;

const DEFAULT_MTU = 23;

export const manager = new BleManager();

export type BlePermission = 'granted' | 'denied' | 'blocked';

export async function requestBlePermissions(): Promise<BlePermission> {
  if (Platform.OS !== 'android') return 'granted';

  const wanted =
    Number(Platform.Version) < 31
      ? [PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION]
      : [PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN, PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT];

  const results = Object.values(await PermissionsAndroid.requestMultiple(wanted));
  if (results.every((v) => v === PermissionsAndroid.RESULTS.GRANTED)) return 'granted';
  return results.includes(PermissionsAndroid.RESULTS.NEVER_ASK_AGAIN) ? 'blocked' : 'denied';
}

export type ScanHit = { id: string; name: string | null; rssi: number | null };

export function scan(onHit: (hit: ScanHit) => void, onError?: (e: Error) => void): () => void {
  manager.startDeviceScan(null, { allowDuplicates: true }, (error, device) => {
    if (error) {
      onError?.(error);
      return;
    }
    const name = device?.name ?? device?.localName ?? null;
    if (!device || !name?.startsWith(CAMERA.name)) return;
    onHit({ id: device.id, name, rssi: device.rssi });
  });

  return () => manager.stopDeviceScan();
}

export type Connection = {
  device: Device;
  maxPayload: number;
  write(to: Endpoint, payload: Uint8Array): Promise<void>;
  request(to: Endpoint, payload: Uint8Array): Promise<void>;
  has(to: Endpoint): Promise<boolean>;
  readRssi(): Promise<number | null>;
  subscribe(
    to: Endpoint,
    onPacket: (bytes: Uint8Array) => void,
    onError?: (e: Error) => void,
  ): Subscription;
  onDisconnect(callback: () => void): Subscription;
  disconnect(): Promise<void>;
};

export async function connect(deviceId: string, wait = false): Promise<Connection> {
  manager.stopDeviceScan();

  let device = await manager.connectToDevice(deviceId, wait ? { autoConnect: true } : { timeout: 10_000 });

  let mtu = DEFAULT_MTU;
  try {
    const negotiated = await device.requestMTU(CAMERA.requestMtu);
    mtu = negotiated.mtu ?? DEFAULT_MTU;
  } catch {
    mtu = DEFAULT_MTU;
  }

  device = await device.discoverAllServicesAndCharacteristics();

  const maxPayload = Math.max(1, mtu - ATT_HEADER_BYTES);

  return {
    device,
    maxPayload,

    async write(to, payload) {
      for (let offset = 0; offset < payload.length; offset += maxPayload) {
        await device.writeCharacteristicWithoutResponseForService(
          to.service,
          to.char,
          bytesToBase64(payload.subarray(offset, offset + maxPayload)),
        );
      }
    },

    async request(to, payload) {
      for (let offset = 0; offset < payload.length; offset += maxPayload) {
        await device.writeCharacteristicWithResponseForService(
          to.service,
          to.char,
          bytesToBase64(payload.subarray(offset, offset + maxPayload)),
        );
      }
    },

    async has(to) {
      const chars = await device.characteristicsForService(to.service).catch(() => []);
      return chars.some((c) => c.uuid.toLowerCase() === to.char.toLowerCase());
    },

    async readRssi() {
      return (await device.readRSSI()).rssi;
    },

    subscribe(to, onPacket, onError) {
      return device.monitorCharacteristicForService(to.service, to.char, (error, characteristic) => {
        if (error) {
          onError?.(error);
          return;
        }
        if (characteristic?.value) onPacket(base64ToBytes(characteristic.value));
      });
    },

    onDisconnect(callback) {
      return device.onDisconnected(() => callback());
    },

    async disconnect() {
      await manager.cancelDeviceConnection(deviceId);
    },
  };
}
