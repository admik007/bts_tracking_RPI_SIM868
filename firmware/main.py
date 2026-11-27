"""Common Pico W bootloader used by all tracker projects.

All local settings (Wi-Fi, OTA and application settings) are stored in config.py.
The bootloader and local config.py are never overwritten by OTA.
"""
import os
import time
import machine
import network
import ujson
import uhashlib
import ubinascii

import config

DEVICE_ID = "".join("{:02x}".format(b) for b in machine.unique_id())
BASE_URL = "http://" + config.HOST.rstrip("/") + "/firmware/" + DEVICE_ID + "/"
PROTECTED = ("main.py", "config.py")
MAX_FILE_BYTES = 70000
LOCAL_MANIFEST = "manifest.json"


def sha256(data):
    return ubinascii.hexlify(uhashlib.sha256(data).digest()).decode()


def fetch(url):
    import urequests
    response = urequests.get(url)
    try:
        if response.status_code != 200:
            raise OSError("HTTP status %s" % response.status_code)
        return response.content
    finally:
        response.close()


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return True

    for attempt in range(2):
        try:
            wlan.connect(config.SSID, config.PASS)
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < 7000:
                if wlan.isconnected():
                    print("Wi-Fi connected:", wlan.ifconfig()[0])
                    return True
                time.sleep_ms(200)
        except Exception as exc:
            print("Wi-Fi error:", exc)

        try:
            wlan.disconnect()
        except Exception:
            pass

    print("Wi-Fi unavailable; local app will run")
    return False


def read_local_version():
    try:
        with open(LOCAL_MANIFEST, "r") as f:
            local_manifest = ujson.loads(f.read())
        return str(local_manifest["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_manifest(manifest):
    # Commit the new version marker only after every firmware file is installed.
    with open(LOCAL_MANIFEST + ".new", "w") as f:
        f.write(ujson.dumps(manifest))

    had_old = False
    try:
        os.remove(LOCAL_MANIFEST + ".bak")
    except OSError:
        pass

    try:
        os.rename(LOCAL_MANIFEST, LOCAL_MANIFEST + ".bak")
        had_old = True
    except OSError:
        pass

    try:
        os.rename(LOCAL_MANIFEST + ".new", LOCAL_MANIFEST)
    except Exception:
        if had_old:
            try:
                os.rename(LOCAL_MANIFEST + ".bak", LOCAL_MANIFEST)
            except OSError:
                pass
        raise

    if had_old:
        try:
            os.remove(LOCAL_MANIFEST + ".bak")
        except OSError:
            pass


def update_firmware():
    base = BASE_URL.rstrip("/")
    raw = fetch(base + "/manifest.json")
    if len(raw) > 10000:
        raise ValueError("manifest too large")

    manifest = ujson.loads(raw)
    version = str(manifest["version"])
    files = manifest["files"]

    if not isinstance(files, dict) or not files:
        raise ValueError("invalid manifest")
    if len(files) > 12:
        raise ValueError("too many files")

    local_version = read_local_version()
    if local_version == version:
        print("Firmware current:", version)
        # Remove obsolete marker left by older bootloader releases.
        for legacy_file in ("version.txt", "manifest.txt"):
            try:
                os.remove(legacy_file)
            except OSError:
                pass
        return

    staged = []
    swapped = []
    backed_up = []

    try:
        # Download and verify every file before replacing anything.
        for name, digest in files.items():
            if (not isinstance(name, str) or not name.endswith(".py")
                    or name.startswith(".") or "/" in name or "\\" in name
                    or name in PROTECTED or ".." in name):
                raise ValueError("disallowed firmware filename: %s" % name)
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("invalid SHA256 for %s" % name)

            data = fetch(base + "/" + name)
            if len(data) > MAX_FILE_BYTES or sha256(data) != digest.lower():
                raise ValueError("SHA256/size mismatch: %s" % name)

            with open(name + ".new", "wb") as f:
                f.write(data)
            staged.append(name)

        # Keep backups so failed swaps can be rolled back.
        for name in staged:
            try:
                os.remove(name + ".bak")
            except OSError:
                pass

            try:
                os.rename(name, name + ".bak")
                backed_up.append(name)
            except OSError:
                pass  # first install

            os.rename(name + ".new", name)
            swapped.append(name)

        save_manifest(manifest)

        # Remove the obsolete version marker after the JSON manifest is committed.
        for legacy_file in ("version.txt", "manifest.txt"):
            try:
                os.remove(legacy_file)
            except OSError:
                pass

        print("Firmware updated to", version)

    except Exception:
        # Roll back all swapped files (including partial installs).
        for name in reversed(swapped):
            try:
                os.remove(name)
            except OSError:
                pass

        for name in reversed(backed_up):
            try:
                os.rename(name + ".bak", name)
            except OSError:
                pass

        for name in staged:
            try:
                os.remove(name + ".new")
            except OSError:
                pass
        try:
            os.remove(LOCAL_MANIFEST + ".new")
        except OSError:
            pass
        raise


def boot():
    # Blink during boot, Wi-Fi check and OTA. app.py takes over LED control.
    led = machine.Pin("LED", machine.Pin.OUT)
    led_timer = machine.Timer(-1)
    led_timer.init(
        period=150,
        mode=machine.Timer.PERIODIC,
        callback=lambda timer: led.toggle()
    )

    # Give Thonny time to attach after Pico starts.
    print("Startup delay: 15 seconds (Thonny connection)")
    time.sleep(15)

    print("Pico DEVICE_ID:", DEVICE_ID)
    print("Firmware URL:", BASE_URL)

    if connect_wifi():
        try:
            update_firmware()
        except Exception as exc:
            print("OTA skipped:", exc)

    led_timer.deinit()
    led.value(0)

    import app
    app.run()


try:
    boot()
except Exception as exc:
    import sys
    sys.print_exception(exc)
    time.sleep(5)
    machine.reset()
