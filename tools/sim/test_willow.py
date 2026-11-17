#!/usr/bin/env python3

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from willow import Component, comp, create, emit, on, prop, ref, state, tick  # noqa: E402


QUEUED_MAX = 64
EVENTS_MAX = 16
TIMERS_MAX = 16


class Clock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms


class Counter(Component):
    n, set_n = state(0)
    other, set_other = state(0)
    runs = 0

    @on("n")
    def watch(self):
        self.runs += 1


class Child(Component):
    value = prop()
    seen = None

    @on("value")
    def watch(self):
        self.seen = self.value


class Parent(Component):
    x, set_x = state(1)
    child = comp(Child, value=lambda self: self.x * 10)


class Debounce(Component):
    text, set_text = state("")
    slow, set_slow = state(None)

    def change(self, v):
        self.set_text(v)
        self.cancel("settle")
        self.remove("settle")
        self.once("settle", lambda _: self.set_slow(v))
        self.after(0.1, "settle")


class Echo(Component):
    heard = None

    @on()
    def listen(self):
        self.bind("ping", self.pinged)
        self.bind("loop", lambda _: self.emit("loop"))

    def pinged(self, payload):
        self.heard = payload


class Listeners(Component):
    log: list = ref(lambda: [])

    @on()
    def listen(self):
        self.once("one", lambda p: self.log.append(("once", p)))
        self.bind("two", self.first)

    def first(self, p):
        self.log.append(("first", p))
        self.bind("two", lambda q: self.log.append(("late", q)))
        self.remove("three")

    def third(self, p):
        self.log.append(("third", p))


class TestWillow(unittest.TestCase):
    def test_setter_lands_at_the_next_tick(self):
        app = create(Counter)
        tick(app)
        app.set_n(5)
        self.assertEqual(app.n, 0)
        tick(app)
        self.assertEqual(app.n, 5)

    def test_on_runs_only_when_its_state_changes(self):
        app = create(Counter)
        tick(app)
        self.assertEqual(app.runs, 1)
        app.set_other(3)
        tick(app)
        self.assertEqual(app.runs, 1)
        app.set_n(1)
        tick(app)
        self.assertEqual(app.runs, 2)
        app.set_n(1)
        tick(app)
        self.assertEqual(app.runs, 2)

    def test_props_are_reread_at_render(self):
        app = create(Parent)
        tick(app)
        self.assertEqual(app.child.seen, 10)
        app.set_x(2)
        tick(app)
        self.assertEqual(app.child.seen, 20)

    def test_emit_runs_listeners_before_it_returns(self):
        app = create(Echo)
        tick(app)
        app.emit("ping", 7)
        self.assertEqual(app.heard, 7)

    def test_nested_emits_raise_on_a_cycle(self):
        app = create(Echo)
        tick(app)
        with self.assertRaisesRegex(RuntimeError, "a cycle"):
            app.emit("loop")

    def test_too_many_updates_before_a_tick_raise(self):
        app = create(Counter)
        tick(app)
        for i in range(QUEUED_MAX):
            app.set_other(i)
        with self.assertRaisesRegex(RuntimeError, "updates before a tick"):
            app.set_other(-1)

    def test_debounce_settles_on_the_last_value(self):
        clock = Clock()
        app = create(Debounce, clock=clock)
        tick(app)
        for t, v in ((0, "a"), (30, "ab"), (60, "abc")):
            clock.ms = t
            app.change(v)
            tick(app)
        for t in range(70, 160, 10):
            clock.ms = t
            tick(app)
            self.assertIsNone(app.slow)
        clock.ms = 160
        tick(app)
        tick(app)
        self.assertEqual(app.slow, "abc")

    def test_a_cancel_with_nothing_pending_does_nothing(self):
        clock = Clock()
        app = create(Debounce, clock=clock)
        tick(app)
        app.change("a")
        clock.ms = 100
        tick(app)
        tick(app)
        self.assertEqual(app.slow, "a")

    def test_once_fires_once(self):
        app = create(Listeners)
        tick(app)
        app.emit("one", 1)
        app.emit("one", 2)
        self.assertEqual(app.log, [("once", 1)])

    def test_a_listener_bound_during_a_firing_hears_the_next_one(self):
        app = create(Listeners)
        tick(app)
        app.emit("two", 1)
        app.emit("two", 2)
        self.assertEqual(app.log, [("first", 1), ("first", 2), ("late", 2)])

    def test_remove_during_a_firing(self):
        app = create(Listeners)
        tick(app)
        app.bind("three", app.third)
        app.emit("two", 1)
        app.emit("three", 2)
        self.assertNotIn(("third", 2), app.log)

    def test_driver_events_wait_for_the_tick_and_refuse_when_full(self):
        app = create(Listeners)
        tick(app)
        self.assertTrue(emit(app, "one", 1))
        self.assertEqual(app.log, [])
        tick(app)
        self.assertEqual(app.log, [("once", 1)])
        for i in range(EVENTS_MAX):
            self.assertTrue(emit(app, "none", i))
        self.assertFalse(emit(app, "none", -1))

    def test_too_many_timers_raise(self):
        app = create(Counter, clock=Clock())
        tick(app)
        for i in range(TIMERS_MAX):
            app.after(1, "t{}".format(i))
        with self.assertRaisesRegex(RuntimeError, "timers pending"):
            app.after(1, "over")


if __name__ == "__main__":
    unittest.main()
