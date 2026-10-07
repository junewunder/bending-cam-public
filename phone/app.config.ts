import type { ExpoConfig } from 'expo/config';
import { withAppBuildGradle, type ConfigPlugin } from 'expo/config-plugins';

const withPublishSigning: ConfigPlugin = (config) =>
  withAppBuildGradle(config, (config) => {
    if (!config.modResults.contents.includes('releaseSigning')) {
      config.modResults.contents += `
if (findProperty('releaseSigning')) {
    def props = new Properties()
    file(findProperty('releaseSigning')).withInputStream { props.load(it) }
    android.signingConfigs.create('published') {
        storeFile file(props.storeFile)
        storePassword props.storePassword
        keyAlias props.keyAlias
        keyPassword props.keyPassword
    }
    android.buildTypes.release.signingConfig android.signingConfigs.published
    android.defaultConfig.versionCode findProperty('versionCode').toInteger()
    android.defaultConfig.versionName findProperty('versionName')
}
`;
    }
    return config;
  });

const config: ExpoConfig = {
  name: 'bendcam',
  slug: 'bendcam',
  scheme: 'bendcam',
  version: '0.1.0',
  orientation: 'portrait',
  userInterfaceStyle: 'dark',
  backgroundColor: '#000000',
  icon: './assets/icon.png',

  android: {
    adaptiveIcon: {
      foregroundImage: './assets/icon.png',
      backgroundColor: '#000000',
    },
    package: 'com.junewunder.bendcam',
    permissions: [
      'android.permission.FOREGROUND_SERVICE',
      'android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE',
      'android.permission.POST_NOTIFICATIONS',
    ],
  },

  plugins: [
    'expo-router',
    [
      'react-native-ble-plx',
      {
        isBackgroundEnabled: false,
        modes: ['central'],
        neverForLocation: true,
        bluetoothAlwaysPermission: 'Allow $(PRODUCT_NAME) to connect to the camera.',
      },
    ],
  ],

  experiments: { typedRoutes: true },
};

export default withPublishSigning(config);
