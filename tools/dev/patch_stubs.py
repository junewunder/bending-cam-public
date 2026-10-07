import sys
import sysconfig
from pathlib import Path

ULAB_ADDITION = '''

def frombuffer(
    buffer: Any,
    *,
    dtype: _DType = ulab.numpy.float,
    count: int = -1,
    offset: int = 0,
) -> ulab.numpy.ndarray:
    """Interpret a buffer as a 1-D array, without copying it."""
    ...
'''


def patch(path: Path, done: str, apply) -> bool:
    if not path.exists():
        print(f"!! not found: {path}", file=sys.stderr)
        return False
    text = path.read_text()
    if done in text:
        print(f"already ok: {path.name}")
        return True
    new = apply(text)
    if new == text:
        print(f"!! could not patch {path} -- upstream stub changed?", file=sys.stderr)
        return False
    path.write_text(new)
    print(f"patched:   {path.name}")
    return True


def main() -> int:
    sp = Path(sysconfig.get_paths()["purelib"])
    ok = patch(
        sp / "ulab-stubs" / "numpy" / "__init__.pyi",
        "def frombuffer(",
        lambda t: t + ULAB_ADDITION,
    )
    ok &= patch(
        sp / "busdisplay-stubs" / "__init__.pyi",
        "root_group: displayio.Group | None",
        lambda t: t.replace(
            "root_group: displayio.Group\n",
            "root_group: displayio.Group | None\n",
        ),
    )
    ok &= patch(
        sp / "ulab-stubs" / "numpy" / "__init__.pyi",
        "def all(",
        lambda t: t + "\n\ndef all(a: Any, *, axis: Optional[int] = None) -> Any: ...\n",
    )
    ok &= patch(
        sp / "ulab-stubs" / "__init__.pyi",
        "__version__: str",
        lambda t: t + "\n__version__: str\n",
    )
    ok &= patch(
        sp / "displayio-stubs" / "__init__.pyi",
        "def __buffer__(",
        lambda t: t.replace(
            "class Bitmap:\n",
            "class Bitmap:\n    def __buffer__(self, flags: int, /) -> memoryview: ...\n",
            1,
        ),
    )
    ok &= patch(
        sp / "sdcardio-stubs" / "__init__.pyi",
        "digitalio.DigitalInOut, digitalio.DigitalInOutProtocol]",
        lambda t: t.replace(
            "cs: Union[microcontroller.Pin, digitalio.DigitalInOutProtocol],",
            "cs: Union[microcontroller.Pin, digitalio.DigitalInOut, "
            "digitalio.DigitalInOutProtocol],",
        ),
    )
    ok &= patch(
        sp / "_bleio-stubs" / "__init__.pyi",
        "def value(self, value: ReadableBuffer)",
        lambda t: t.replace(
            '    value: bytearray\n    """The value of this characteristic."""\n',
            "    @property\n    def value(self) -> bytearray: ...\n"
            "    @value.setter\n    def value(self, value: ReadableBuffer) -> None: ...\n",
            1,
        ),
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
