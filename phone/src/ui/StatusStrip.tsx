import { usePathname, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useLink, useStills } from '../camera/CameraProvider';
import type { LinkStatus } from '../camera/link';
import { theme } from '../theme';

const WORDS: Record<LinkStatus, string> = {
  scanning: 'pick a camera',
  looking: 'looking…',
  'not-found': 'not found',
  connecting: 'connecting…',
  connected: 'connected',
  reconnecting: 'reconnecting…',
  'bluetooth-off': 'bluetooth off',
  'no-permission': 'no bluetooth permission',
  stopped: 'off',
};

export function StatusStrip() {
  const link = useLink();
  const arriving = useStills().arriving;
  const router = useRouter();
  const path = usePathname();
  const insets = useSafeAreaInsets();
  const up = link.status === 'connected';
  const trying = link.status === 'connecting' || link.status === 'reconnecting' || link.status === 'looking';

  return (
    <Pressable
      style={[styles.strip, { paddingTop: insets.top + 6 }, up && styles.up]}
      onPress={() => path !== '/camera' && router.push('/camera')}
    >
      <View style={[styles.dot, up ? styles.dotUp : trying ? styles.dotTrying : styles.dotDown]} />
      <Text style={[styles.text, up && styles.textUp]} numberOfLines={1}>
        {WORDS[link.status]}
        {link.camera && link.status !== 'scanning' ? ` · ${link.camera.name ?? link.camera.id}` : ''}
      </Text>
      <View style={styles.spacer} />
      {arriving && up && (
        <Text style={[styles.text, styles.textUp, styles.fixed]} numberOfLines={1}>
          ↓{arriving.size ? Math.floor((arriving.got * 100) / arriving.size) : 100}%
        </Text>
      )}
      {link.fake && <Text style={[styles.tag, up && styles.tagUp]}>FAKE</Text>}
      {link.rssi != null && up && (
        <Text style={[styles.text, styles.textUp, styles.fixed]} numberOfLines={1}>
          {link.rssi} dBm
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  strip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingBottom: 10,
    backgroundColor: theme.surface,
    borderBottomColor: theme.border,
    borderBottomWidth: 2,
  },
  up: { backgroundColor: theme.accent, borderBottomColor: theme.accent },
  dot: { width: 12, height: 12 },
  dotUp: { backgroundColor: theme.onAccent },
  dotTrying: { backgroundColor: theme.accent },
  dotDown: { backgroundColor: theme.danger },
  text: { color: theme.text, fontFamily: theme.font, fontSize: 15, flexShrink: 1 },
  textUp: { color: theme.onAccent, fontWeight: '700' },
  tag: {
    color: theme.accent,
    fontFamily: theme.font,
    fontSize: 12,
    fontWeight: '700',
    borderColor: theme.accent,
    borderWidth: 1,
    paddingHorizontal: 4,
  },
  tagUp: { color: theme.onAccent, borderColor: theme.onAccent },
  fixed: { flexShrink: 0 },
  spacer: { flex: 1 },
});
