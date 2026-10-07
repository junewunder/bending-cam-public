function uuid(n: number): string {
  return `b3c1${n.toString(16).padStart(4, '0')}-5eed-4a11-8c4e-6c0ffee00001`;
}

export type Endpoint = { service: string; char: string };

export const CAMERA = {
  name: 'bendcam',

  stills: { service: uuid(1), char: uuid(2) } satisfies Endpoint,

  ack: { service: uuid(4), char: uuid(3) } satisfies Endpoint,

  settings: { service: uuid(5), char: uuid(6) } satisfies Endpoint,

  requestMtu: 517,
} as const;
