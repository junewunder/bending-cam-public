import { type ReactNode, useMemo, useRef, useState } from 'react';
import { Alert, PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';

import type { Setting, Value } from '../camera/protocol';
import { type Pending, show } from '../camera/settings';
import { theme } from '../theme';

type RowProps = {
  setting: Setting;
  value: Value | undefined;
  pending: Pending | undefined;
  note: string | undefined;
  disabled: boolean;
  blocked: string | null;
  live: Value | undefined;
  onChange(v: Value): void;
  onAct(): void;
};

export function SettingRow(props: RowProps) {
  const p = {
    ...props,
    disabled: props.disabled || props.blocked != null,
    value: props.blocked != null && props.live !== undefined ? props.live : props.value,
  };
  const { setting: s } = p;
  const asking = p.pending?.v !== undefined ? show(s, p.pending.v) : null;

  return (
    <View style={[styles.row, p.disabled && styles.disabled]}>
      {s.kind !== 'action' && (
        <View style={styles.head}>
          <Text style={styles.label}>{s.label}</Text>
          {s.when === 'next shot' && <Text style={styles.badge}>NEXT SHOT</Text>}
          <View style={styles.spacer} />
          {p.value !== undefined && <Text style={styles.value}>{show(s, p.value)}</Text>}
        </View>
      )}

      {s.kind === 'enum' && (
        <Segments
          opts={s.opts}
          value={p.value as number | undefined}
          ghost={p.pending?.v as number | undefined}
          disabled={p.disabled}
          onPick={p.onChange}
        />
      )}
      {s.kind === 'int' && (
        <Slider
          min={s.min}
          max={s.max}
          step={s.step ?? 1}
          value={p.value as number | undefined}
          ghost={p.pending?.v as number | undefined}
          disabled={p.disabled}
          onCommit={p.onChange}
        />
      )}
      {s.kind === 'bool' && (
        <Toggle
          value={p.value as boolean | undefined}
          pending={p.pending != null}
          disabled={p.disabled}
          onFlip={() => p.onChange(!p.value)}
        />
      )}
      {s.kind === 'action' && (
        <Button
          label={p.pending ? `${s.label}…` : s.label}
          disabled={p.disabled || p.pending != null}
          onPress={() => (s.confirm ? confirm(s.label, 'Do it', p.onAct) : p.onAct())}
        />
      )}

      {}
      <Text style={styles.note} numberOfLines={1}>
        {asking != null ? `asking for ${asking}…` : (p.note ?? p.blocked ?? ' ')}
      </Text>
    </View>
  );
}

export function confirm(title: string, yes: string, then: () => void) {
  Alert.alert(title, undefined, [
    { text: 'Cancel', style: 'cancel' },
    { text: yes, style: 'destructive', onPress: then },
  ]);
}

export function Segments(p: {
  opts: string[];
  value: number | undefined;
  ghost: number | undefined;
  disabled: boolean;
  onPick(i: number): void;
}) {
  return (
    <View style={styles.segments}>
      {p.opts.map((opt, i) => {
        const on = i === p.value;
        const ghost = i === p.ghost && !on;
        return (
          <Pressable
            key={opt}
            disabled={p.disabled}
            onPress={() => i !== p.value && p.onPick(i)}
            style={({ pressed }) => [
              styles.segment,
              on && styles.segmentOn,
              ghost && styles.segmentGhost,
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.segmentText, on && styles.segmentTextOn]}>{opt}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function Toggle(p: { value: boolean | undefined; pending: boolean; disabled: boolean; onFlip(): void }) {
  return (
    <Pressable
      disabled={p.disabled || p.pending}
      onPress={p.onFlip}
      style={({ pressed }) => [styles.toggle, p.value && styles.toggleOn, pressed && styles.pressed]}
    >
      <View style={[styles.knob, p.value ? styles.knobOn : styles.knobOff, p.pending && styles.knobPending]} />
      <Text style={[styles.toggleText, p.value && styles.segmentTextOn]}>{p.value ? 'on' : 'off'}</Text>
    </Pressable>
  );
}

function Slider(p: {
  min: number;
  max: number;
  step: number;
  value: number | undefined;
  ghost: number | undefined;
  disabled: boolean;
  onCommit(v: number): void;
}) {
  const [width, setWidth] = useState(1);
  const [drag, setDrag] = useState<number | null>(null);
  const live = useRef(p);
  live.current = p;
  const widthRef = useRef(width);
  widthRef.current = width;

  const snap = (v: number) => {
    const { min, max, step } = live.current;
    return Math.min(max, Math.max(min, min + Math.round((v - min) / step) * step));
  };
  const at = (x: number) => {
    const { min, max } = live.current;
    return snap(min + (Math.max(0, Math.min(x, widthRef.current)) / widthRef.current) * (max - min));
  };

  const responder = useMemo(() => {
    let grantX = 0;
    let grantDx = 0;
    let last: number | null = null;
    return PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) =>
        !live.current.disabled && Math.abs(g.dx) > 6 && Math.abs(g.dx) > Math.abs(g.dy),
      onPanResponderTerminationRequest: () => false,
      onPanResponderGrant: (e, g) => {
        grantX = e.nativeEvent.locationX;
        grantDx = g.dx;
        last = at(grantX);
        setDrag(last);
      },
      onPanResponderMove: (_, g) => {
        last = at(grantX + g.dx - grantDx);
        setDrag(last);
      },
      onPanResponderRelease: () => {
        if (last != null && last !== live.current.value) live.current.onCommit(last);
        last = null;
        setDrag(null);
      },
      onPanResponderTerminate: () => {
        last = null;
        setDrag(null);
      },
    });
  }, []);

  const frac = (v: number) => (p.max === p.min ? 0 : (v - p.min) / (p.max - p.min));
  const ghost = drag ?? p.ghost;
  const nudge = (d: number) => {
    const from = p.ghost ?? p.value ?? p.min;
    const to = snap(from + d * p.step);
    if (to !== p.value) p.onCommit(to);
  };

  return (
    <View style={styles.sliderRow}>
      <StepButton label="−" disabled={p.disabled} onPress={() => nudge(-1)} />
      <View
        style={styles.track}
        onLayout={(e) => setWidth(Math.max(1, e.nativeEvent.layout.width))}
        {...responder.panHandlers}
      >
        <View pointerEvents="none" style={styles.rail} />
        {p.value !== undefined && (
          <View pointerEvents="none" style={[styles.fill, { width: frac(p.value) * width }]} />
        )}
        {p.value !== undefined && (
          <View pointerEvents="none" style={[styles.thumb, { left: frac(p.value) * width - 6 }]} />
        )}
        {ghost != null && ghost !== p.value && (
          <View pointerEvents="none" style={[styles.thumb, styles.thumbGhost, { left: frac(ghost) * width - 6 }]}>
            <Text style={styles.ghostLabel}>{ghost}</Text>
          </View>
        )}
      </View>
      <StepButton label="+" disabled={p.disabled} onPress={() => nudge(1)} />
    </View>
  );
}

function StepButton(p: { label: string; disabled: boolean; onPress(): void }) {
  return (
    <Pressable
      disabled={p.disabled}
      onPress={p.onPress}
      style={({ pressed }) => [styles.step, pressed && styles.pressed]}
    >
      <Text style={styles.stepText}>{p.label}</Text>
    </Pressable>
  );
}

export function Button(p: {
  label: string;
  onPress(): void;
  disabled?: boolean;
  kind?: 'primary' | 'plain' | 'danger';
}) {
  const kind = p.kind ?? 'plain';
  return (
    <Pressable
      disabled={p.disabled}
      onPress={p.onPress}
      style={({ pressed }) => [
        styles.button,
        kind === 'primary' && styles.buttonPrimary,
        kind === 'danger' && styles.buttonDanger,
        p.disabled && styles.disabled,
        pressed && styles.pressed,
      ]}
    >
      <Text
        style={[
          styles.buttonText,
          kind === 'primary' && styles.segmentTextOn,
          kind === 'danger' && styles.dangerText,
        ]}
      >
        {p.label}
      </Text>
    </Pressable>
  );
}

export function Section(p: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{p.title.toUpperCase()}</Text>
      {p.children}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 2,
    padding: 12,
    gap: 10,
  },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.6 },
  spacer: { flex: 1 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  label: { color: theme.text, fontFamily: theme.font, fontSize: 17, fontWeight: '700', flexShrink: 1 },
  value: { color: theme.accent, fontFamily: theme.font, fontSize: 17, fontWeight: '700' },
  badge: {
    color: theme.accent,
    borderColor: theme.accent,
    borderWidth: 1,
    fontFamily: theme.font,
    fontSize: 11,
    paddingHorizontal: 4,
  },
  note: { color: theme.muted, fontFamily: theme.font, fontSize: 13 },

  segments: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  segment: {
    minHeight: theme.target,
    minWidth: theme.target,
    flexGrow: 1,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: theme.border,
    borderWidth: 2,
  },
  segmentOn: { backgroundColor: theme.accent, borderColor: theme.accent },
  segmentGhost: { borderColor: theme.accent, borderStyle: 'dashed', borderRadius: 1 },
  segmentText: { color: theme.text, fontFamily: theme.font, fontSize: 16 },
  segmentTextOn: { color: theme.onAccent, fontWeight: '700' },

  toggle: {
    height: theme.target,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 8,
    borderColor: theme.border,
    borderWidth: 2,
  },
  toggleOn: { backgroundColor: theme.accent, borderColor: theme.accent },
  knob: { width: 36, height: 36 },
  knobOn: { backgroundColor: theme.onAccent },
  knobOff: { backgroundColor: theme.muted },
  knobPending: { opacity: 0.35 },
  toggleText: { color: theme.text, fontFamily: theme.font, fontSize: 16 },

  sliderRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  step: {
    width: theme.target,
    height: theme.target,
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: theme.border,
    borderWidth: 2,
  },
  stepText: { color: theme.text, fontFamily: theme.font, fontSize: 24 },
  track: { flex: 1, height: theme.target, justifyContent: 'center' },
  rail: { height: 4, backgroundColor: theme.border },
  fill: { position: 'absolute', height: 4, backgroundColor: theme.accent },
  thumb: {
    position: 'absolute',
    top: 8,
    width: 12,
    height: theme.target - 16,
    backgroundColor: theme.accent,
  },
  thumbGhost: {
    backgroundColor: 'transparent',
    borderColor: theme.accent,
    borderWidth: 2,
    overflow: 'visible',
  },
  ghostLabel: {
    position: 'absolute',
    top: -20,
    left: -14,
    width: 40,
    textAlign: 'center',
    color: theme.accent,
    fontFamily: theme.font,
    fontSize: 13,
  },

  button: {
    minHeight: theme.target,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    borderColor: theme.accent,
    borderWidth: 2,
  },
  buttonPrimary: { backgroundColor: theme.accent },
  buttonDanger: { borderColor: theme.danger },
  buttonText: { color: theme.accent, fontFamily: theme.font, fontSize: 16, fontWeight: '700' },
  dangerText: { color: theme.danger },

  section: { gap: 8 },
  sectionTitle: {
    color: theme.muted,
    fontFamily: theme.font,
    fontSize: 13,
    letterSpacing: 2,
    marginTop: 8,
  },
});
