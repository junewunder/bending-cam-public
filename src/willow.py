# pyright: reportAttributeAccessIssue=false

_QMAX = 64
_EMAX = 16
_TMAX = 16
_DMAX = 8
_SLOTS = 30

_TICKS_MASK = (1 << 29) - 1
_TICKS_HALF = 1 << 28

_count = 0
_RESERVED = ("rendered", "app", "mount", "render", "bind", "once", "cancel", "remove",
             "after", "emit", "set_timeout", "clear_timeout")


def _next():
    global _count
    _count += 1
    return _count


class _Mark:
    def __init__(self):
        self.n = _next()


class _State(_Mark):
    def __init__(self, default):
        super().__init__()
        self.default = default


class _SetterMark:
    def __init__(self, st):
        self.st = st


class _Ref(_Mark):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn


class _Prop(_Mark):
    pass


class _Comp(_Mark):
    def __init__(self, cls, props):
        super().__init__()
        self.cls = cls
        self.props = props


class _On(_Mark):
    def __init__(self, fn, names):
        super().__init__()
        self.fn = fn
        self.names = names


def state(default):
    st = _State(default)
    return st, _SetterMark(st)


def ref(fn):
    return _Ref(fn)


def prop():
    return _Prop()


def comp(cls, **props):
    return _Comp(cls, props)


def on(*names):
    def wrap(fn):
        return _On(fn, names)

    return wrap


class Component:
    def mount(self):
        pass

    def render(self):
        return None

    def bind(self, label, fn):
        self._w_root.listen(label, fn, True)

    def once(self, label, fn):
        self._w_root.listen(label, fn, False)

    def cancel(self, label):
        self._w_root.unschedule(label)

    def remove(self, label):
        self._w_root.unlisten(label)

    def emit(self, label, payload=None):
        self._w_root.dispatch(label, payload)

    def after(self, secs, label, payload=None):
        r = self._w_root
        r.schedule(label, (r.clock() + int(secs * 1000)) & _TICKS_MASK, payload)

    def set_timeout(self, label, secs, fn):
        self.once(label, fn)
        self.after(secs, label)

    def clear_timeout(self, label):
        self.cancel(label)
        self.remove(label)


class _Meta:

    def __init__(self, cls):
        marks = []
        setters = {}
        for name in dir(cls):
            v = getattr(cls, name)
            if isinstance(v, _Mark):
                marks.append((v.n, name, v))
            elif isinstance(v, _SetterMark):
                setters[v.st] = name
        marks.sort(key=lambda m: m[0])
        where = "{}.{}".format
        for _, name, _ in marks:
            if name in _RESERVED:
                raise TypeError(where(cls.__name__, name) + ": the runtime's own name")
        self.states = []
        self.props = []
        self.inits = []
        self.steps = []
        bits = {}
        for _, name, v in marks:
            if isinstance(v, _State):
                if v not in setters:
                    raise TypeError(where(cls.__name__, name) +
                                    ": unpack state() into a value and a setter")
                bits[name] = len(bits)
                self.states.append((bits[name], name, setters[v], v.default))
            elif isinstance(v, _Prop):
                bits[name] = len(bits)
                self.props.append((bits[name], name))
        if len(bits) > _SLOTS:
            raise TypeError("{}: over {} states and props".format(cls.__name__, _SLOTS))
        for _, name, v in marks:
            if isinstance(v, _On):
                mask = 0
                for w in v.names:
                    if w not in bits:
                        raise TypeError("{} watches {}: not a state or prop".format(
                            where(cls.__name__, name), w))
                    mask |= 1 << bits[w]
                self.steps.append((v.fn, mask))
            elif isinstance(v, _Comp):
                self.inits.append((name, v))
                self.steps.append((name, None))
            elif isinstance(v, _Ref):
                self.inits.append((name, v))


_metas = {}


def _meta(cls):
    m = _metas.get(cls)
    if m is None:
        m = _metas[cls] = _Meta(cls)
    return m


class Setter:
    def __init__(self, root, inst, slot, name):
        self.root = root
        self.inst = inst
        self.bit = 1 << slot
        self.name = name

    def __call__(self, v):
        r = self.root
        n = r.qn
        if n == _QMAX:
            raise RuntimeError("willow: over {} updates before a tick".format(_QMAX))
        r.qa[n] = self
        r.qb[n] = v
        r.qn = n + 1


def _no_clock():
    raise RuntimeError("willow: a timer needs create(cls, clock=...)")


class _Root:
    def __init__(self, clock):
        self.clock = clock or _no_clock
        self.qn = 0
        self.qa = [None] * _QMAX
        self.qb = [None] * _QMAX
        self.qold = [None] * _QMAX
        self.qfirst = [False] * _QMAX
        self.en = 0
        self.el = [None] * _EMAX
        self.ev = [None] * _EMAX
        self.tn = 0
        self.tl = [None] * _TMAX
        self.tt = [0] * _TMAX
        self.tv = [None] * _TMAX
        self.tg = [0] * _TMAX
        self.gen = 0
        self.soonest = 0
        self.listeners = {}
        self.depth = 0
        self.spent = False

    def emit(self, label, payload):
        n = self.en
        if n == _EMAX:
            return False
        self.el[n] = label
        self.ev[n] = payload
        self.en = n + 1
        return True

    def build(self, cls, parent, propfns):
        m = _meta(cls)
        inst = cls()
        inst._w_meta = m
        inst._w_root = self
        inst._w_parent = parent
        inst._w_propfns = propfns
        inst._w_changed = 0
        inst._w_touched = 0
        inst._w_first = True
        inst.rendered = None
        inst.app = parent.app if parent else inst
        for slot, name, setter, default in m.states:
            setattr(inst, name, default() if callable(default) else default)
            setattr(inst, setter, Setter(self, inst, slot, name))
        for _, name in m.props:
            if name not in propfns:
                raise TypeError("{} needs prop {}".format(cls.__name__, name))
            setattr(inst, name, propfns[name](parent))
        for name, v in m.inits:
            if isinstance(v, _Ref):
                setattr(inst, name, v.fn())
            else:
                setattr(inst, name, self.build(v.cls, inst, v.props))
        return inst

    def fire_due(self):
        if not self.tn:
            return
        now = self.clock()
        if (now - self.soonest) & _TICKS_MASK >= _TICKS_HALF:
            return
        tl = self.tl
        tt = self.tt
        tg = self.tg
        gen = self.gen
        while self.tn:
            best = -1
            late = -1
            for i in range(_TMAX):
                if tl[i] is None or tg[i] == gen:
                    continue
                d = (now - tt[i]) & _TICKS_MASK
                if d < _TICKS_HALF and d > late:
                    best = i
                    late = d
            if best < 0:
                self.reckon(now)
                return
            label = tl[best]
            payload = self.tv[best]
            tl[best] = self.tv[best] = None
            self.tn -= 1
            self.dispatch(label, payload)

    def reckon(self, now):
        tl = self.tl
        tt = self.tt
        first = -1
        for i in range(_TMAX):
            if tl[i] is not None and (first < 0 or (tt[i] - tt[first]) & _TICKS_MASK >= _TICKS_HALF):
                first = i
        if first >= 0:
            self.soonest = tt[first]

    def schedule(self, label, at, payload):
        tl = self.tl
        for i in range(_TMAX):
            if tl[i] is None:
                tl[i] = label
                self.tt[i] = at
                self.tv[i] = payload
                self.tg[i] = self.gen
                if not self.tn or (at - self.soonest) & _TICKS_MASK >= _TICKS_HALF:
                    self.soonest = at
                self.tn += 1
                return
        raise RuntimeError("willow: over {} timers pending".format(_TMAX))

    def unschedule(self, label):
        tl = self.tl
        tt = self.tt
        first = -1
        for i in range(_TMAX):
            if tl[i] == label and (first < 0 or (tt[i] - tt[first]) & _TICKS_MASK >= _TICKS_HALF):
                first = i
        if first >= 0:
            tl[first] = self.tv[first] = None
            self.tn -= 1

    def listen(self, label, fn, persistent):
        ls = self.listeners.get(label)
        if ls is None:
            ls = self.listeners[label] = []
        ls.append(fn)
        ls.append(persistent)

    def unlisten(self, label):
        ls = self.listeners.get(label)
        if ls:
            for i in range(0, len(ls), 2):
                ls[i] = None
            self.spent = True
            if not self.depth:
                self.compact()

    def dispatch(self, label, payload):
        ls = self.listeners.get(label)
        if not ls:
            return
        if self.depth == _DMAX:
            raise RuntimeError("willow: {} firings nested at {}: a cycle".format(_DMAX, label))
        self.depth += 1
        try:
            for i in range(0, len(ls), 2):
                fn = ls[i]
                if fn is None:
                    continue
                if not ls[i + 1]:
                    ls[i] = None
                    self.spent = True
                fn(payload)
        finally:
            self.depth -= 1
        if self.spent and not self.depth:
            self.compact()

    def compact(self):
        self.spent = False
        for ls in self.listeners.values():
            j = 0
            for i in range(0, len(ls), 2):
                if ls[i] is not None:
                    ls[j] = ls[i]
                    ls[j + 1] = ls[i + 1]
                    j += 2
            while len(ls) > j:
                ls.pop()

    def flush(self):
        self.gen = (self.gen + 1) & _TICKS_MASK
        el = self.el
        ev = self.ev
        for i in range(self.en):
            self.dispatch(el[i], ev[i])
            el[i] = ev[i] = None
        self.en = 0
        self.run(0)
        n = self.qn
        self.fire_due()
        self.run(n)
        qa = self.qa
        qb = self.qb
        qold = self.qold
        qfirst = self.qfirst
        for i in range(self.qn):
            s = qa[i]
            inst = s.inst
            if qfirst[i] and qold[i] != getattr(inst, s.name):
                inst._w_changed |= s.bit
            inst._w_touched = 0
            qa[i] = qb[i] = qold[i] = None
        self.qn = 0

    def run(self, i):
        qa = self.qa
        qb = self.qb
        qold = self.qold
        qfirst = self.qfirst
        while i < self.qn:
            s = qa[i]
            inst = s.inst
            cur = getattr(inst, s.name)
            qfirst[i] = not inst._w_touched & s.bit
            if qfirst[i]:
                inst._w_touched |= s.bit
                qold[i] = cur
            v = qb[i]
            setattr(inst, s.name, v(cur) if callable(v) else v)
            i += 1

    def render(self, inst):
        first = inst._w_first
        for a, mask in inst._w_meta.steps:
            if mask is None:
                child = getattr(inst, a)
                self.reprop(child)
                self.render(child)
            elif first or inst._w_changed & mask:
                a(inst)
        inst.rendered = inst.render()
        inst._w_changed = 0
        if first:
            inst._w_first = False
            inst.mount()

    def reprop(self, child):
        fns = child._w_propfns
        parent = child._w_parent
        for slot, name in child._w_meta.props:
            v = fns[name](parent)
            if v != getattr(child, name):
                setattr(child, name, v)
                child._w_changed |= 1 << slot


def create(cls, clock=None):
    root = _Root(clock)
    return root.build(cls, None, {})


def start(cls, clock=None):
    app = create(cls, clock)
    tick(app)
    return app


def emit(app, label, payload=None):
    return app._w_root.emit(label, payload)


def tick(app):
    root = app._w_root
    root.flush()
    root.render(app)
