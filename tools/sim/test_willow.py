#!/usr/bin/env python3

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from willow import Component, comp, create, on, prop, state, tick  # noqa: E402


QUEUED_MAX = 64


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


if __name__ == "__main__":
    unittest.main()
