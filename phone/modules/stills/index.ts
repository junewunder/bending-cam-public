import { requireNativeModule } from 'expo';

type StillsModule = {
  dir(): string;
  list(uri: string): string[];
  save(uri: string, bytes: Uint8Array): void;
  toJpeg(bmp: string, jpg: string, quality: number): Promise<void>;
  toGallery(jpg: string, album: string): Promise<string>;
};

export default requireNativeModule<StillsModule>('Stills');
