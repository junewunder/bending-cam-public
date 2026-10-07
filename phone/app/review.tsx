import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useCamera, useLink, useReview, useStills } from '../src/camera/CameraProvider';
import type { StillsState } from '../src/camera/stills';
import { theme } from '../src/theme';
import { Button, Section } from '../src/ui/controls';

export default function ReviewScreen() {
  const { review } = useCamera();
  const link = useLink();
  const rv = useReview();
  const st = useStills();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    review.enter();
    return () => review.exit();
  }, [review]);

  const shot = rv.shot;
  const on = rv.phase === 'on' && shot != null;
  const screen = shot?.files.find((f) => f.includes('_screen'));
  const full = shot?.files.find((f) => !f.includes('_screen'));
  const missing = (f: string | undefined) => f != null && !st.have.has(f) && !st.asked.has(f);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.inner, { paddingBottom: insets.bottom + 24 }]}
    >
      <Button kind="primary" label="‹ Settings" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />

      <View style={styles.card}>
        <Text style={styles.name}>{on ? shot.shot : rv.phase === 'opening' ? 'Opening review…' : 'Not reviewing'}</Text>
        <Text style={styles.meta}>
          {on ? `${shot.i} of ${shot.n}, oldest first` : 'The camera shows its preview.'}
          {rv.waiting && on ? ' · …' : ''}
        </Text>
        {rv.note && <Text style={styles.error}>{rv.note}</Text>}
      </View>

      {on ? (
        <View style={styles.arrows}>
          <Arrow label="‹" hint="older" disabled={shot.i <= 1} onPress={() => review.step(-1)} />
          <Arrow label="›" hint="newer" disabled={shot.i >= shot.n} onPress={() => review.step(1)} />
        </View>
      ) : (
        rv.phase === 'off' && (
          <Button
            kind="primary"
            label="Review the card"
            disabled={link.status !== 'connected'}
            onPress={() => review.enter()}
          />
        )
      )}

      {on && (
        <Section title="On this phone">
          {!screen && <FileRow name={`${shot.shot}_screen.bmp`} status="not on the card" />}
          {shot.files.map((f) => (
            <FileRow key={f} name={f} status={fileStatus(f, st)} />
          ))}
          {!full && <FileRow name={`${shot.shot}.bmp`} status="not on the card" />}

          {missing(screen) && <Button label="Get the preview" onPress={() => review.get([screen!])} />}
          {missing(full) && (
            <Button
              label={missing(screen) ? 'Get the preview and the full still' : 'Get the full still'}
              onPress={() => review.get([screen, full].filter((f): f is string => missing(f)))}
            />
          )}
          {st.arriving && !shot.files.includes(st.arriving.name) && st.asked.size > 0 && (
            <Text style={styles.meta}>Asked-for files come after {st.arriving.name}, arriving now.</Text>
          )}
        </Section>
      )}
    </ScrollView>
  );
}

function fileStatus(name: string, st: StillsState): string {
  if (st.arriving?.name === name) {
    const pct = st.arriving.size ? Math.floor((st.arriving.got * 100) / st.arriving.size) : 100;
    return `arriving, ${pct}%`;
  }
  if (st.have.has(name)) return 'on the phone';
  if (st.asked.has(name)) return 'asked for, queued on the camera';
  return 'not yet';
}

function FileRow(p: { name: string; status: string }) {
  const here = p.status === 'on the phone';
  return (
    <View style={styles.row}>
      <Text style={styles.file} numberOfLines={1}>
        {p.name}
      </Text>
      <Text style={[styles.status, !here && styles.muted]}>{here ? `✓ ${p.status}` : p.status}</Text>
    </View>
  );
}

function Arrow(p: { label: string; hint: string; disabled: boolean; onPress(): void }) {
  return (
    <Pressable
      disabled={p.disabled}
      onPress={p.onPress}
      style={({ pressed }) => [styles.arrow, p.disabled && styles.disabled, pressed && styles.pressed]}
    >
      <Text style={styles.arrowText}>{p.label}</Text>
      <Text style={styles.arrowHint}>{p.hint}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  inner: { padding: 12, gap: 12 },
  card: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 14,
    gap: 6,
  },
  name: { color: theme.text, fontFamily: theme.font, fontSize: 24, fontWeight: '700' },
  meta: { color: theme.muted, fontFamily: theme.font, fontSize: 13 },
  error: { color: theme.danger, fontFamily: theme.font, fontSize: 14 },
  arrows: { flexDirection: 'row', gap: 12 },
  arrow: {
    flex: 1,
    height: theme.target * 3,
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: theme.accent,
    borderWidth: 2,
  },
  arrowText: { color: theme.accent, fontFamily: theme.font, fontSize: 72, lineHeight: 80 },
  arrowHint: { color: theme.accent, fontFamily: theme.font, fontSize: 14 },
  disabled: { opacity: 0.3 },
  pressed: { opacity: 0.6, backgroundColor: theme.surface },
  row: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 10,
    gap: 2,
  },
  file: { color: theme.text, fontFamily: theme.font, fontSize: 15, fontWeight: '700' },
  status: { color: theme.accent, fontFamily: theme.font, fontSize: 13 },
  muted: { color: theme.muted },
});
