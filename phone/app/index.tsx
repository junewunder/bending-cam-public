import { useRouter } from 'expo-router';
import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useCamera, useLink, useSettings, useStills } from '../src/camera/CameraProvider';
import { requires } from '../src/camera/settings';
import { PROTO, type Setting } from '../src/camera/protocol';
import { theme } from '../src/theme';
import { Button, Section, SettingRow, confirm } from '../src/ui/controls';

export default function SettingsScreen() {
  const cam = useCamera();
  const { settings } = cam;
  const link = useLink();
  const st = useSettings();
  const stills = useStills();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const live = st.phase === 'ready';
  const groups = groupRows(st.rows);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.inner, { paddingBottom: insets.bottom + 24 }]}
    >
      <Button
        label={stills.arriving ? `Stills › ${stills.arriving.name}` : 'Stills ›'}
        onPress={() => router.push('/stills')}
      />
      <Button label="Review ›" disabled={!live} onPress={() => router.push('/review')} />
      {st.phase === 'idle' && (
        <Message text={idleText(link.status)}>
          {link.status === 'no-permission' ? (
            <Button kind="primary" label="Allow Bluetooth" onPress={() => cam.allow()} />
          ) : (
            <Button kind="primary" label="Camera" onPress={() => router.push('/camera')} />
          )}
        </Message>
      )}
      {st.phase === 'loading' && st.rows.length === 0 && (
        <Message text="Reading the camera's settings…" />
      )}
      {st.phase === 'unsupported' && (
        <Message text="Connected, but this camera's firmware has no settings yet." />
      )}
      {st.phase === 'wrong-proto' && (
        <Message
          text={`The camera speaks settings protocol ${st.proto}; this app speaks ${PROTO}. Update whichever is older.`}
        />
      )}
      {st.phase === 'failed' && (
        <Message text={st.error ?? "The camera's settings didn't arrive."}>
          <Button kind="primary" label="Try again" onPress={() => settings.load()} />
        </Message>
      )}
      {st.phase === 'offline' && (
        <Text style={styles.banner}>Not live: these are the settings from before the link dropped.</Text>
      )}

      {groups.map(([group, rows]) => (
        <Section key={group} title={group}>
          {rows.map((s) => (
            <SettingRow
              key={s.k}
              setting={s}
              value={st.values[s.k]}
              pending={st.pending[s.k]}
              note={st.notes[s.k]}
              disabled={!live}
              blocked={requires(s, st.rows, st.values)}
              live={st.live[s.k]}
              onChange={(v) => settings.change(s.k, v)}
              onAct={() => settings.act(s.k)}
            />
          ))}
        </Section>
      ))}

      {st.rows.length > 0 && (
        <View style={styles.footer}>
          <Button
            kind="danger"
            label="Reset to defaults"
            disabled={!live}
            onPress={() => confirm('Reset every setting to its default?', 'Reset', () => settings.resetAll())}
          />
        </View>
      )}
    </ScrollView>
  );
}

function groupRows(rows: Setting[]): [string, Setting[]][] {
  const out = new Map<string, Setting[]>();
  for (const r of rows) {
    const g = r.group ?? 'Settings';
    out.set(g, [...(out.get(g) ?? []), r]);
  }
  return [...out];
}

function idleText(status: string): string {
  if (status === 'bluetooth-off') return 'Bluetooth is off.';
  if (status === 'no-permission') {
    return (
      'The app needs the Nearby devices permission to reach the camera. ' +
      "If Allow opens Android's settings instead, go to Permissions, Nearby devices. " +
      "On Android 17 it can say Allow while Bluetooth is still refused: pick Don't allow, then Allow."
    );
  }
  if (status === 'scanning') return 'No camera chosen yet.';
  return 'Waiting for the camera. Is it on?';
}

function Message(p: { text: string; children?: ReactNode }) {
  return (
    <View style={styles.message}>
      <Text style={styles.messageText}>{p.text}</Text>
      {p.children}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  inner: { padding: 12, gap: 12 },
  message: { gap: 16, paddingVertical: 24 },
  messageText: { color: theme.text, fontFamily: theme.font, fontSize: 17, lineHeight: 24 },
  banner: {
    color: theme.onAccent,
    backgroundColor: theme.danger,
    fontFamily: theme.font,
    fontSize: 14,
    padding: 10,
  },
  footer: { marginTop: 16 },
});
