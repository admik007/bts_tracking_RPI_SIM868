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
RESTART_INTERVAL_MS = 60 * 60 * 1000
SEND_DELAY_MIN_MS = 5000
SEND_DELAY_MAX_MS = 12000
WATCHDOG_TIMEOUT_MS = 7500
WATCHDOG_FEED_INTERVAL_MS = 250


def sleep_with_watchdog(wdt, duration_ms):
    """Sleep in short chunks so legitimate waits never starve the WDT."""
    remaining = max(0, int(duration_ms))
    while remaining:
        chunk = min(WATCHDOG_FEED_INTERVAL_MS, remaining)
        wdt.feed()
        time.sleep_ms(chunk)
        remaining -= chunk
    wdt.feed()


def connect_receiver(wlan, wdt):
    # Disconnect any infrastructure Wi-Fi used by main.py for the OTA check.
    if wlan.isconnected():
        try:
            wlan.disconnect()
        except OSError:
            pass
    wlan.active(True)
    print("Connecting to receiver AP:", RECEIVER_SSID)
    try:
        wlan.connect(RECEIVER_SSID)
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < WIFI_CONNECT_MS:
            if wlan.isconnected():
                print("Receiver Wi-Fi connected:", wlan.ifconfig())
                return True
            sleep_with_watchdog(wdt, 200)
    except OSError as exc:
        print("Receiver Wi-Fi error:", exc)
    print("Receiver AP unavailable; measurements continue locally")
    return False


def send_record(wlan, record, wdt):
    if not wlan.isconnected():
        return False
    sock = None
    try:
        payload = (ujson.dumps(record) + "\n").encode("utf-8")
        sock = socket.socket()
        sock.settimeout(TCP_TIMEOUT_S)
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
    led = machine.Pin("LED", machine.Pin.OUT)
    wlan = network.WLAN(network.STA_IF)
    wdt = machine.WDT(timeout=WATCHDOG_TIMEOUT_MS)
    sim = SIM868(wdt)
    boot_started = time.ticks_ms()
    led.value(0)
    print("BTS TRACKING publisher, Pico:", DEVICE_ID)

    def modem_error():
        # Three short flashes, then a pause before repeating.
        for _ in range(3):
            led.value(1)
            sleep_with_watchdog(wdt, 100)
            led.value(0)
            sleep_with_watchdog(wdt, 100)
        sleep_with_watchdog(wdt, 900)

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
                sleep_with_watchdog(wdt, send_delay)

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
            sleep_with_watchdog(wdt, min(interval_ms - elapsed, restart_remaining))
        if time.ticks_diff(time.ticks_ms(), boot_started) >= RESTART_INTERVAL_MS:
            print("Hourly restart: resetting Pico")
            machine.reset()
