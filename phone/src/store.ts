import { File, Paths } from 'expo-file-system';

export type Prefs = {
  camera: { id: string; name: string | null } | null;
  fake: boolean;
  stills: 'none' | 'screens' | 'all';
};

const DEFAULTS: Prefs = { camera: null, fake: false, stills: 'all' };

const file = new File(Paths.document, 'prefs.json');

export function loadPrefs(): Prefs {
  try {
    if (!file.exists) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(file.textSync()) };
  } catch {
    return DEFAULTS;
  }
}

export function savePrefs(update: Partial<Prefs>): Prefs {
  const next = { ...loadPrefs(), ...update };
  try {
    file.write(JSON.stringify(next));
  } catch {
  }
  return next;
}
