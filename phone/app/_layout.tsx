import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';

import { CameraProvider } from '../src/camera/CameraProvider';
import { theme } from '../src/theme';
import { StatusStrip } from '../src/ui/StatusStrip';

export default function RootLayout() {
  return (
    <CameraProvider>
      <StatusBar style="light" />
      <View style={{ flex: 1, backgroundColor: theme.bg }}>
        <StatusStrip />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: theme.bg },
            animation: 'none',
          }}
        />
      </View>
    </CameraProvider>
  );
}
