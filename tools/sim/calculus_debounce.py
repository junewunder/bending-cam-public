#!/usr/bin/env python3

from collections import Counter


def run(keys, horizon=1000, step=10):
    listeners = {}
    cancels = Counter()
    timers = []
    value = slow = None
    seen = object()
    log = []
    queue = []
    for t in range(0, horizon, step):
        value = keys.get(t, value)
        if value != seen:
            seen = value
            queue += [("cancel", "timeout"), ("remove", "timeout"),
                      ("listen", "timeout", ("set_slow", value)), ("after", "timeout", t + 100)]
        due = sorted(d for d in timers if d[0] <= t)
        timers = [d for d in timers if d[0] > t]
        work = [("fire", label) for _, label in due] + queue
        queue = []
        for item in work:
            kind = item[0]
            if kind == "fire":
                if cancels[item[1]]:
                    cancels[item[1]] -= 1
                    log.append((t, "firing cancelled"))
                    continue
                work.extend(listeners.pop(item[1], []))
            elif kind == "cancel":
                cancels[item[1]] += 1
            elif kind == "remove":
                listeners[item[1]] = []
            elif kind == "listen":
                listeners.setdefault(item[1], []).append(item[2])
            elif kind == "after":
                timers.append((item[2], item[1]))
            elif kind == "set_slow":
                slow = item[1]
                log.append((t, "slow = {!r}".format(slow)))
    return slow, log


if __name__ == "__main__":
    for name, keys in (("one keystroke", {0: "a"}),
                       ("a, b, c, then nothing", {0: "a", 30: "b", 60: "c"})):
        slow, log = run(keys)
        print("{}: slow ends {!r}; {}".format(name, slow, log))
