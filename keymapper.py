"""
keymapper.py - WASD joystick + mouse-look + button mapping for Android emulators.
Sends real multitouch over ADB through minitouch. No recoil/aim assistance of any kind.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time

from pynput import keyboard, mouse

CFG = "keymap.json"
DEFAULT = {
    "adb": "adb",
    "serial": "127.0.0.1:5555",          # FILL: adb port of your emulator
    "width": 1280,
    "height": 720,                       # emulator resolution (landscape)
    "rotation": 90,                      # 0 | 90 | 270; flip 90<->270 if axes come out mirrored
    "toggle_key": "f1",
    "quit_key": "f12",
    "sens_keys": {"f2": "hip", "f3": "ads", "f4": "scope"},
    "joystick": {"center": [200, 540], "radius": 110},
    "look": {"center": [960, 360], "margin": 90,
             "sens": {"hip": 1.0, "ads": 0.6, "scope": 0.4}},
    "keys": {
        "space": [1180, 520], "c": [1100, 620], "z": [1180, 620], "r": [900, 620],
        "1": [500, 680], "2": [600, 680], "3": [700, 680], "f": [1050, 420],
        "tab": [1200, 60], "g": [1000, 150], "q": [320, 330], "e": [440, 330],
    },
    "mouse": {"left": [1090, 330], "right": [1180, 200]},   # fire, ads
}


def load_cfg():
    if os.path.exists(CFG):
        with open(CFG, encoding="utf-8") as f:
            return {**DEFAULT, **json.load(f)}
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(DEFAULT, f, indent=2)
    return DEFAULT


cfg = load_cfg()
W, H = cfg["width"], cfg["height"]
lock = threading.Lock()
sock = None
touch_max = (W, H)
WASD = set("wasd")


def adb(*a, **k):
    return subprocess.Popen([cfg["adb"], "-s", cfg["serial"], *a], **k)


def connect():
    global sock, touch_max
    subprocess.run([cfg["adb"], "connect", cfg["serial"]], capture_output=True)
    subprocess.run([cfg["adb"], "-s", cfg["serial"], "forward", "tcp:1111",
                    "localabstract:minitouch"], check=True)
    adb("shell", "/data/local/tmp/minitouch",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        try:
            sock = socket.create_connection(("127.0.0.1", 1111), timeout=2)
            break
        except OSError:
            time.sleep(0.25)
    else:
        sys.exit("minitouch not reachable: push the binary first (see README)")
    hdr = sock.makefile("r")
    for _ in range(3):
        line = hdr.readline().split()
        if line and line[0] == "^":
            touch_max = (int(line[2]), int(line[3]))


def tp(x, y):
    """landscape screen px -> touch panel coords"""
    mx, my = touch_max
    r = cfg["rotation"]
    if r == 0:
        return int(x * mx / W), int(y * my / H)
    if r == 90:
        return int(y * mx / H), int((W - x) * my / W)
    return int((H - y) * mx / H), int(x * my / W)


def send(s):
    with lock:
        sock.sendall(s.encode())


def down(i, x, y):
    tx, ty = tp(x, y)
    send(f"d {i} {tx} {ty} 50\nc\n")


def move(i, x, y):
    tx, ty = tp(x, y)
    send(f"m {i} {tx} {ty} 50\nc\n")


def up(i):
    send(f"u {i}\nc\n")


# ---- state ----
enabled = False
held = set()           # mapped buttons currently pressed
wasd_held = set()      # movement keys currently pressed
contacts = {}          # button name -> contact id (2+)
joy_down = False
look = {"x": 0, "y": 0, "down": False, "anchor": (0, 0), "mode": "hip"}
mctl = mouse.Controller()


def cid(name):
    return contacts.setdefault(name, 2 + len(contacts))


def press(name, pos):
    if name in held:
        return
    held.add(name)
    down(cid(name), *pos)


def release(name):
    if name not in held:
        return
    held.discard(name)
    up(cid(name))


def update_joy():
    global joy_down
    dx = ("d" in wasd_held) - ("a" in wasd_held)
    dy = ("s" in wasd_held) - ("w" in wasd_held)
    jc, jr = cfg["joystick"]["center"], cfg["joystick"]["radius"]
    if dx == 0 and dy == 0:
        if joy_down:
            up(0)
            joy_down = False
        return
    n = (dx * dx + dy * dy) ** 0.5
    x, y = jc[0] + dx / n * jr, jc[1] + dy / n * jr
    (move if joy_down else down)(0, x, y)
    joy_down = True


def look_start():
    c = cfg["look"]["center"]
    look.update(x=c[0], y=c[1], down=True, anchor=mctl.position)
    down(1, *c)


def look_stop():
    if look["down"]:
        up(1)
        look["down"] = False


def release_all():
    for n in list(held):
        release(n)
    wasd_held.clear()
    update_joy()
    look_stop()


def on_move(px, py):
    if not (enabled and look["down"]):
        return
    ax, ay = look["anchor"]
    if (px, py) == (ax, ay):
        return
    s = cfg["look"]["sens"][look["mode"]]
    look["x"] += (px - ax) * s
    look["y"] += (py - ay) * s
    mctl.position = (ax, ay)                      # recenter -> relative motion
    m, c = cfg["look"]["margin"], cfg["look"]["center"]
    if not (m < look["x"] < W - m and m < look["y"] < H - m):
        up(1)                                     # lift + replant before the edge
        look["x"], look["y"] = c
        down(1, *c)
    else:
        move(1, look["x"], look["y"])


def kname(k):
    ch = getattr(k, "char", None)
    return ch.lower() if ch else getattr(k, "name", "") or ""


def shutdown():
    release_all()
    os._exit(0)


def on_press(k):
    global enabled
    n = kname(k)
    if n == cfg["quit_key"]:
        shutdown()
    if n == cfg["toggle_key"]:
        enabled = not enabled
        if enabled:
            look_start()
        else:
            release_all()
        print("ON" if enabled else "OFF")
        return
    if not enabled:
        return
    if n in cfg["sens_keys"]:
        look["mode"] = cfg["sens_keys"][n]
        print("sens:", look["mode"])
        return
    if n in WASD:
        wasd_held.add(n)
        update_joy()
        return
    if n in cfg["keys"]:
        press(n, cfg["keys"][n])


def on_release(k):
    n = kname(k)
    if not enabled:
        return
    if n in WASD:
        wasd_held.discard(n)
        update_joy()
        return
    if n in cfg["keys"]:
        release(n)


def on_click(x, y, b, pressed):
    if not enabled or b.name not in cfg["mouse"]:
        return
    (press if pressed else release)("m_" + b.name, cfg["mouse"][b.name])


def main():
    connect()
    print(f"touch panel {touch_max}; F1 toggle, F2/F3/F4 sens, F12 quit")
    keyboard.Listener(on_press=on_press, on_release=on_release).start()
    with mouse.Listener(on_move=on_move, on_click=on_click) as l:
        l.join()


if __name__ == "__main__":
    main()
