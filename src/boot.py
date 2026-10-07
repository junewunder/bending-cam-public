import microcontroller
import storage

_NVM_DEV_ONCE = 0x96
_DEV_ONCE = 0xD5

nvm = microcontroller.nvm
if nvm is not None and len(nvm) > _NVM_DEV_ONCE and nvm[_NVM_DEV_ONCE] == _DEV_ONCE:
    nvm[_NVM_DEV_ONCE] = 0
    print("boot.py: dev mode (just devmode)")
else:
    storage.disable_usb_drive()
    storage.remount("/", readonly=False)
    print("boot.py: field mode, no CIRCUITPY on USB")
