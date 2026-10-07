import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useCamera, useLink } from '../src/camera/CameraProvider';
import { theme } from '../src/theme';
import { Button, Section, confirm } from '../src/ui/controls';

export default function CameraScreen() {
  const cam = useCamera();
  const link = useLink();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const others = link.hits.filter((h) => h.id !== link.camera?.id);
  const looking = link.status === 'scanning' || link.status === 'not-found' || link.status === 'looking';

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.inner, { paddingBottom: insets.bottom + 24 }]}
    >
      <Button kind="primary" label="‹ Settings" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />

      {link.camera && (
        <Section title="This camera">
          <View style={styles.card}>
            <Text style={styles.title}>{link.camera.name ?? '(unnamed)'}</Text>
            <Text style={styles.meta}>{link.camera.id}</Text>
            <Text style={styles.meta}>
              {link.status}
              {link.rssi != null ? ` · ${link.rssi} dBm` : ''}
              {link.status === 'connected' && !link.hasSettings ? ' · no settings service' : ''}
            </Text>
            {link.error && <Text style={styles.error}>{link.error}</Text>}
          </View>
          {!cam.fake && (
            <Button
              kind="danger"
              label="Forget this camera"
              onPress={() => confirm('Forget this camera?', 'Forget', () => cam.link.forget())}
            />
          )}
        </Section>
      )}

      {!cam.fake && (looking || others.length > 0) && (
        <Section title={link.camera ? 'Other cameras' : 'Cameras nearby'}>
          {others.length === 0 && <Text style={styles.meta}>Looking… is the camera on?</Text>}
          {others.map((hit) => (
            <Pressable
              key={hit.id}
              style={({ pressed }) => [styles.card, pressed && styles.pressed]}
              onPress={() => cam.link.choose(hit)}
            >
              <Text style={styles.title}>{hit.name ?? '(unnamed)'}</Text>
              <Text style={styles.meta}>
                {hit.id} · {hit.rssi ?? '?'} dBm
              </Text>
            </Pressable>
          ))}
        </Section>
      )}

      {link.status === 'bluetooth-off' && <Text style={styles.error}>Bluetooth is off.</Text>}
      {link.status === 'no-permission' && (
        <>
          <Text style={styles.error}>No Nearby devices permission.</Text>
          <Button kind="primary" label="Allow Bluetooth" onPress={() => cam.allow()} />
        </>
      )}

      <Section title="Developer">
        <View style={styles.switchRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Fake camera</Text>
            <Text style={styles.meta}>A table in the phone, in place of the radio.</Text>
          </View>
          <Switch
            value={cam.fake}
            onValueChange={cam.setFake}
            trackColor={{ false: theme.border, true: theme.accent }}
            thumbColor={theme.text}
          />
        </View>
        {cam.link.simulateDrop && (
          <Button label="Drop the link, as a reset would" onPress={() => cam.link.simulateDrop?.()} />
        )}
        {cam.link.shoot && <Button label="Take a still (two files)" onPress={() => cam.link.shoot?.()} />}
      </Section>
    </ScrollView>
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
    gap: 4,
    minHeight: theme.target,
  },
  pressed: { opacity: 0.6 },
  title: { color: theme.text, fontFamily: theme.font, fontSize: 17, fontWeight: '700' },
  meta: { color: theme.muted, fontFamily: theme.font, fontSize: 13 },
  error: { color: theme.danger, fontFamily: theme.font, fontSize: 14 },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 14,
  },
});
