import microcontroller
import supervisor
from supervisor import SafeModeReason

BOOTLOOP_LIMIT = 3

RESET_ON = (
    SafeModeReason.HARD_FAULT,
    SafeModeReason.WATCHDOG,
    SafeModeReason.SDK_FATAL_ERROR,
    SafeModeReason.STACK_OVERFLOW,
    SafeModeReason.NLR_JUMP_FAIL,
    SafeModeReason.INTERRUPT_ERROR,
    SafeModeReason.GC_ALLOC_OUTSIDE_VM,
    SafeModeReason.BROWNOUT,
)

_NVM_BASE = 0x80
_NVM_MAGIC = b"\xbc\x03"
_OFF_CRASHES = 3
_OFF_BOOTLOOP = 4
_OFF_SAFE_NEW = 5
_OFF_SAFE_REASON = 6
_NVM_LEN = 22

reason = supervisor.runtime.safe_mode_reason
name = str(reason).split(".")[-1]
print("safemode.py:", name)

nvm = microcontroller.nvm
st = bytearray(nvm[_NVM_BASE : _NVM_BASE + _NVM_LEN])
if st[:2] != _NVM_MAGIC:
    st = bytearray(_NVM_MAGIC) + bytearray(_NVM_LEN - 2)
st[_OFF_SAFE_REASON : _OFF_SAFE_REASON + 16] = name.encode()[:16] + bytes(16 - min(len(name), 16))
st[_OFF_SAFE_NEW] = 1

resetting = reason in RESET_ON and st[_OFF_BOOTLOOP] < BOOTLOOP_LIMIT
if reason in RESET_ON:
    st[_OFF_CRASHES] = (st[_OFF_CRASHES] + 1) & 0xFF
    st[_OFF_BOOTLOOP] = min(st[_OFF_BOOTLOOP] + 1, 0xFF)
nvm[_NVM_BASE : _NVM_BASE + _NVM_LEN] = st

if resetting:
    print("resetting ({} in a row)".format(st[_OFF_BOOTLOOP]))
    microcontroller.reset()
print("staying in safe mode ({} crashes in a row)".format(st[_OFF_BOOTLOOP]))
