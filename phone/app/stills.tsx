import { useRouter } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useCamera, useKeepAliveError, useLink, useStills } from '../src/camera/CameraProvider';
import { type Mode, type Received, describe } from '../src/camera/stills';
import { theme } from '../src/theme';
import { Button, Section, Segments } from '../src/ui/controls';

const MODES: Mode[] = ['none', 'screens', 'all'];

export default function StillsScreen() {
  const { stills } = useCamera();
  const link = useLink();
  const st = useStills();
  const keepAliveError = useKeepAliveError();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const a = st.arriving;

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.inner, { paddingBottom: insets.bottom + 24 }]}
    >
      <Button kind="primary" label="‹ Settings" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />

      <Section title="Take from the camera">
        <View style={styles.card}>
          <Segments
            opts={['none', 'previews', 'everything']}
            value={MODES.indexOf(st.mode)}
            ghost={undefined}
            disabled={false}
            onPick={(i) => stills.setMode(MODES[i])}
          />
          <Text style={styles.meta}>
            {MODE_TEXT[st.mode]}
          </Text>
        </View>
      </Section>

      <Section title="Arriving">
        <View style={styles.card}>
          {a ? (
            <>
              <Text style={styles.title}>{a.name}</Text>
              <View style={styles.bar}>
                <View style={[styles.fill, { width: `${a.size ? (a.got * 100) / a.size : 100}%` }]} />
              </View>
              <Text style={styles.meta}>
                {Math.round(a.got / 1024)} / {Math.round(a.size / 1024)} KB
              </Text>
              <Text style={styles.meta}>{describe(a)}</Text>
            </>
          ) : (
            <Text style={styles.meta}>
              {!st.available
                ? link.status === 'connected'
                  ? "This camera's firmware sends no stills."
                  : 'Not connected.'
                : 'Nothing arriving. The camera sends each still it saves, from this power-up.'}
            </Text>
          )}
          {keepAliveError && (
            <Text style={styles.error}>
              Couldn't keep the app awake ({keepAliveError}). Leave it open until the still arrives.
            </Text>
          )}
        </View>
      </Section>

      {st.recent.length > 0 && (
        <Section title="This session">
          {st.recent.map((r) => (
            <View key={r.name} style={styles.row}>
              <Text style={styles.name} numberOfLines={1}>
                {r.name}
              </Text>
              <Text style={[styles.status, r.status === 'failed' && styles.error]}>{WORDS[r.status]}</Text>
              <Text style={styles.meta}>{detail(r)}</Text>
            </View>
          ))}
        </Section>
      )}
    </ScrollView>
  );
}

const MODE_TEXT: Record<Mode, string> = {
  none: 'Only what you ask for in Review. Everything else stays queued on the camera until a connection that takes it.',
  screens:
    'The 320×240 preview copies only, ~8 s each. Full stills stay queued on the camera until a connection that takes everything.',
  all: 'Every still, the full size too: ~77 s for one at XGA.',
};

const WORDS: Record<Received['status'], string> = {
  skipped: 'left on the camera',
  saved: 'saved, JPEG next',
  converting: 'making the JPEG…',
  done: 'in the gallery',
  failed: 'failed',
};

function detail(r: Received): string {
  const parts = [`${Math.round(r.size / 1024)} KB`];
  if (r.seconds) parts.push(`${r.seconds.toFixed(1)} s`, `${(r.size / 1024 / r.seconds).toFixed(1)} KB/s`);
  if (r.error) parts.push(r.error);
  return parts.join(' · ');
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  inner: { padding: 12, gap: 12 },
  card: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 14,
    gap: 8,
  },
  title: { color: theme.text, fontFamily: theme.font, fontSize: 17, fontWeight: '700' },
  meta: { color: theme.muted, fontFamily: theme.font, fontSize: 13 },
  error: { color: theme.danger, fontFamily: theme.font, fontSize: 13 },
  bar: { height: 16, borderColor: theme.border, borderWidth: 2 },
  fill: { height: '100%', backgroundColor: theme.accent },
  row: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 10,
    gap: 2,
  },
  name: { color: theme.text, fontFamily: theme.font, fontSize: 15, fontWeight: '700' },
  status: { color: theme.accent, fontFamily: theme.font, fontSize: 13 },
});
