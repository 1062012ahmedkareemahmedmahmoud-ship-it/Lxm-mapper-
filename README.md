# keymapper

Keyboard + mouse to touch mapper for Android emulators. WASD drives a virtual joystick, the mouse drives camera look, and keys map to on-screen buttons. Input is sent as real multitouch over ADB via [minitouch](https://github.com/openstf/minitouch).

No aim assistance, no recoil compensation. It only translates your input.

## Setup

1. Install Python 3.9+ and ADB, then `pip install -r requirements.txt`.
2. Get the `minitouch` binary matching your emulator ABI (`adb shell getprop ro.product.cpu.abi`) from [minitouch-prebuilt](https://github.com/openstf/minitouch-prebuilt), then:
   ```
   adb -s 127.0.0.1:PORT push minitouch /data/local/tmp/
   adb -s 127.0.0.1:PORT shell chmod 755 /data/local/tmp/minitouch
   ```
3. Run `python keymapper.py`. First run generates `keymap.json`.
4. Edit `keymap.json`: set `serial`, `width`/`height`, and tune each button coordinate from a screenshot of your HUD.

## Controls

| Key | Action |
|---|---|
| F1 | toggle on/off (mouse locks to look while on) |
| F2 / F3 / F4 | sensitivity profile: hip / ads / scope |
| F12 | quit |

## Notes

- Axes mirrored? Change `rotation` from 90 to 270.
- Disable any built-in keymapping in the emulator to avoid double input.
- Using external input on emulators can violate a game's ToS. Your account, your risk.
