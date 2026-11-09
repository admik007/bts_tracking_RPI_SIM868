"""BTS Tracking publisher: SIM868 readings plus TCP delivery to central AP.

main.py still performs the existing infrastructure Wi-Fi / OTA check first.
After boot, this app connects to BTS-TRACKING and sends JSON lines to receiver.
No local queue yet: measurements stay visible on USB serial on a network failure.
"""
import machine
import time
import random
import ujson
import ubinascii
import network
import socket
import config
from sim868 import SIM868

DEVICE_ID = ubinascii.hexlify(machine.unique_id()).decode()
RECEIVER_SSID = "BTS-TRACKING"
RECEIVER_IP = "192.168.4.1"
RECEIVER_PORT = 5000
WIFI_RETRY_MS = 20000
WIFI_CONNECT_MS = 7000
TCP_TIMEOUT_S = 3
WDT_TIMEOUT_MS = 8000  # RP2040 watchdog limit is approximately 8.3 seconds.


def sleep_with_wdt(wdt, duration_ms):
    """Sleep in short chunks while keeping the hardware watchdog serviced."""
    remaining = int(duration_ms)
    while remaining > 0:
        wdt.feed()
        chunk = min(1000, remaining)
        time.sleep_ms(chunk)
        remaining -= chunk
    wdt.feed()
RESTART_INTERVAL_MS = 60 * 60 * 1000
SEND_DELAY_MIN_MS = 5000
SEND_DELAY_MAX_MS = 12000


def connect_receiver(wlan, wdt):
    # Fully disconnect from the infrastructure AP before joining the receiver.
    print("Switching Wi-Fi to receiver AP:", RECEIVER_SSID)
    try:
        try:
            wlan.disconnect()
        except OSError:
            pass

        # disconnect() is asynchronous on RP2: wait for the old link to drop.
        start = time.ticks_ms()
        while wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start) < 5000:
            wdt.feed()
            time.sleep_ms(100)

        wlan.active(False)
        sleep_with_wdt(wdt, 1500)
        wlan.active(True)
        sleep_with_wdt(wdt, 500)

        for attempt in range(2):
            # Do not let connect() silently keep using the previous AP.
            # Scan and connect to the receiver by its exact BSSID.
            wdt.feed()
            aps = wlan.scan()
            receiver_aps = []
            for ap in aps:
                try:
                    ssid = ap[0].decode("utf-8")
                except AttributeError:
                    ssid = ap[0]
                if ssid == RECEIVER_SSID:
                    receiver_aps.append(ap)

            if not receiver_aps:
                print("Receiver AP not found in Wi-Fi scan")
            else:
                # Prefer the strongest receiver AP if more than one is visible.
                target = max(receiver_aps, key=lambda item: item[3])
                bssid = target[1]
                print("Receiver AP found: BSSID=%s RSSI=%s channel=%s" % (
                    ubinascii.hexlify(bssid).decode(), target[3], target[2]))
                wlan.connect(RECEIVER_SSID, bssid=bssid)

                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < WIFI_CONNECT_MS:
                    wdt.feed()
                    if wlan.isconnected():
                        ip_config = wlan.ifconfig()
                        ip = ip_config[0]
                        if ip.startswith("192.168.4.") and ip != "192.168.4.1":
                            print("Receiver Wi-Fi connected:", ip_config)
                            return True
                        print("Connected but IP is not from receiver AP:", ip_config)
                        break
                    time.sleep_ms(200)

            try:
                wlan.disconnect()
            except OSError:
                pass
            start = time.ticks_ms()
            while wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start) < 3000:
                wdt.feed()
                time.sleep_ms(100)
            if attempt == 0:
                wlan.active(False)
                sleep_with_wdt(wdt, 1000)
                wlan.active(True)
                sleep_with_wdt(wdt, 500)

    except OSError as exc:
        print("Receiver Wi-Fi setup error:", exc)

    print("Receiver AP unavailable or invalid DHCP address; measurements continue locally")
    return False

def send_record(wlan, record, wdt):
    if not wlan.isconnected():
        return False
    sock = None
    try:
        payload = (ujson.dumps(record) + "\n").encode("utf-8")
        sock = socket.socket()
        sock.settimeout(TCP_TIMEOUT_S)
        wdt.feed()
        sock.connect((RECEIVER_IP, RECEIVER_PORT))
        wdt.feed()
        sock.sendall(payload)
        wdt.feed()
        ack = sock.recv(16)
        wdt.feed()
        if ack.strip() != b"OK":
            print("Receiver rejected record:", ack)
            return False
        return True
    except OSError as exc:
        print("Receiver TCP error:", exc)
        return False
    finally:
        if sock is not None:
            sock.close()


def run():
    # RP2040 WDT resets the Pico only if application progress stops.
    wdt = machine.WDT(timeout=WDT_TIMEOUT_MS)
    led = machine.Pin("LED", machine.Pin.OUT)
    wlan = network.WLAN(network.STA_IF)
    sim = SIM868(wdt)
    boot_started = time.ticks_ms()
    led.value(0)
    print("BTS TRACKING publisher, Pico:", DEVICE_ID)

    def modem_error():
        # Three short flashes, then a pause before repeating.
        for _ in range(3):
            led.value(1)
            sleep_with_wdt(wdt, 100)
            led.value(0)
            sleep_with_wdt(wdt, 100)
        sleep_with_wdt(wdt, 900)

    # The SIM868 measurement loop must still function without the receiver.
    if not sim.start():
        print("SIM868 did not respond; retrying periodically")
        modem_error()

    # Switch from the OTA infrastructure Wi-Fi to the receiver AP explicitly.
    connect_receiver(wlan, wdt)
    next_wifi_attempt = time.ticks_add(time.ticks_ms(), WIFI_RETRY_MS)
    interval_ms = max(1000, int(config.SAMPLE_SECONDS * 1000))
    while True:
        started = time.ticks_ms()
        try:
            wdt.feed()
            if not wlan.isconnected() and time.ticks_diff(started, next_wifi_attempt) >= 0:
                connect_receiver(wlan, wdt)
                next_wifi_attempt = time.ticks_add(time.ticks_ms(), WIFI_RETRY_MS)

            cell = sim.cell()
            # Each sender may provide the shared GPS master fix when available.
            gps = sim.gnss()
            record = {"device": DEVICE_ID, "source": "bts_pico_sim868"}
            record.update(cell)
            record.update(gps)
            print("BTS_JSON:" + ujson.dumps(record))

            if wlan.isconnected():
                send_delay = random.randint(
                    SEND_DELAY_MIN_MS, SEND_DELAY_MAX_MS)
                print("Receiver send delay: %d ms" % send_delay)
                sleep_with_wdt(wdt, send_delay)

            if wlan.isconnected():
                # LED is on only while the TCP record is being transmitted.
                led.value(1)
                try:
                    sent = send_record(wlan, record, wdt)
                finally:
                    led.value(0)
            else:
                sent = False

            if sent:
                print("Receiver ACK: OK")
            else:
                print("Receiver delivery not confirmed (no local queue yet)")

            if cell["cellid"] is None and not sim.start():
                print("SIM868 reinit unsuccessful")
                modem_error()
        except Exception as exc:
            print("Measurement error:", exc)

        elapsed = time.ticks_diff(time.ticks_ms(), started)
        restart_remaining = RESTART_INTERVAL_MS - time.ticks_diff(
            time.ticks_ms(), boot_started)
        if restart_remaining <= 0:
            print("Hourly restart: resetting Pico")
            machine.reset()

        if elapsed < interval_ms:
            sleep_with_wdt(wdt, min(interval_ms - elapsed, restart_remaining))
        if time.ticks_diff(time.ticks_ms(), boot_started) >= RESTART_INTERVAL_MS:
            print("Hourly restart: resetting Pico")
            machine.reset()
