"""BTS Tracking central AP receiver with SD-backed JSONL storage.

The unchanged main.py performs infrastructure Wi-Fi / OTA at boot; this app
switches to the open BTS-TRACKING AP and accepts JSON lines over TCP.
Each accepted record is appended to /sd/pending.jsonl before replying OK.
No LCD or MQTT yet. No flash fallback: a failed SD write returns ERR sd.
"""
import network
import socket
import time
import ujson
import machine
import os
import config
import sdcard

AP_SSID = "BTS-TRACKING"
AP_IP = "192.168.4.1"
LISTEN_PORT = 5000
MAX_LINE_BYTES = 2048
SD_MOUNT = "/sd"
QUEUE_PATH = "/sd/pending.jsonl"

# Standard SPI0 wiring for an SD module; override in local config.py.
# NOTE: GP17 is also a button on some ST7735 LCD boards: do NOT share CS.
SD_SPI_ID = getattr(config, "SD_SPI_ID", 0)
SD_SCK_PIN = getattr(config, "SD_SCK_PIN", 18)
SD_MOSI_PIN = getattr(config, "SD_MOSI_PIN", 19)
SD_MISO_PIN = getattr(config, "SD_MISO_PIN", 16)
SD_CS_PIN = getattr(config, "SD_CS_PIN", 17)
SD_BAUDRATE = getattr(config, "SD_BAUDRATE", 1_000_000)

sd_ready = False
sd_fault = None
records_saved = 0
_sd_spi = None
_sd_device = None


def mount_sd():
    global sd_ready, sd_fault, _sd_spi, _sd_device
    try:
        _sd_spi = machine.SPI(
            SD_SPI_ID, baudrate=SD_BAUDRATE, polarity=0, phase=0,
            sck=machine.Pin(SD_SCK_PIN),
            mosi=machine.Pin(SD_MOSI_PIN),
            miso=machine.Pin(SD_MISO_PIN))
        _sd_device = sdcard.SDCard(
            _sd_spi, machine.Pin(SD_CS_PIN, machine.Pin.OUT))
        os.mount(os.VfsFat(_sd_device), SD_MOUNT)
        # Verify write access up front; never format the card automatically.
        with open(QUEUE_PATH, "a") as out:
            pass
        sd_ready = True
        sd_fault = None
        print("SD mounted:", SD_MOUNT)
        print("MQTT pending queue:", QUEUE_PATH)
        return True
    except Exception as exc:
        sd_ready = False
        sd_fault = str(exc)
        print("SD ERROR (mount/write test):", sd_fault)
        return False


def save_record(record):
    global sd_ready, sd_fault, records_saved
    if not sd_ready:
        return False
    try:
        # A full JSON object per newline survives restart and can be replayed.
        # Open/close on every record, so OK means the file was closed normally.
        line = ujson.dumps(record) + "\n"
        with open(QUEUE_PATH, "a") as out:
            out.write(line)
            out.flush()
        records_saved += 1
        sd_fault = None
        return True
    except Exception as exc:
        sd_ready = False
        sd_fault = str(exc)
        print("SD ERROR (append):", sd_fault)
        # Deliberately do not acknowledge this record.
        return False


def start_ap():
    sta = network.WLAN(network.STA_IF)
    try:
        sta.disconnect()
    except OSError:
        pass
    sta.active(False)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, security=0)
    ap.ifconfig((AP_IP, "255.255.255.0", AP_IP, "0.0.0.0"))
    for _ in range(50):
        if ap.active():
            break
        time.sleep_ms(100)

    print("================================")
    print("BTS TRACKING - CENTRAL AP")
    print("================================")
    print("SSID:", AP_SSID)
    print("IP configuration:", ap.ifconfig())
    print("AP active:", ap.active())
    print("SD ready:", sd_ready)
    print("================================")
    return ap


def parse_record(line):
    if line.startswith(b"BTS_JSON:"):
        line = line[len(b"BTS_JSON:"):]
    record = ujson.loads(line.decode("utf-8"))
    if not isinstance(record, dict):
        raise ValueError("JSON object required")
    if not record.get("device"):
        raise ValueError("missing device")
    return record


def handle_client(client, address):
    print("Connected:", address)
    client.settimeout(5)
    pending = b""
    try:
        while True:
            try:
                chunk = client.recv(512)
            except OSError:
                break
            if not chunk:
                break
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                if len(line) > MAX_LINE_BYTES:
                    print("Rejected oversized message:", address)
                    client.send(b"ERR size\n")
                    return
                try:
                    record = parse_record(line)
                except (ValueError, TypeError, UnicodeError) as exc:
                    print("Invalid record:", exc)
                    client.send(b"ERR json\n")
                    continue
                if save_record(record):
                    print("SD SAVED #{}: {}".format(records_saved, ujson.dumps(record)))
                    client.send(b"OK\n")
                else:
                    print("SD unavailable; record not acknowledged:", sd_fault)
                    client.send(b"ERR sd\n")
            if len(pending) > MAX_LINE_BYTES:
                print("Rejected oversized message:", address)
                client.send(b"ERR size\n")
                break
    finally:
        client.close()
        print("Disconnected:", address)


def run():
    led = machine.Pin("LED", machine.Pin.OUT)
    mount_sd()
    ap = start_ap()
    address = socket.getaddrinfo("0.0.0.0", LISTEN_PORT)[0][-1]
    server = socket.socket()
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(address)
        server.listen(4)
        server.settimeout(2)
        print("Receiver listening on", AP_IP, "port", LISTEN_PORT)
        while True:
            try:
                client, peer = server.accept()
            except OSError:
                led.toggle()
                continue
            try:
                handle_client(client, peer)
            except Exception as exc:
                print("Client error:", exc)
                try:
                    client.close()
                except OSError:
                    pass
    finally:
        server.close()
        ap.active(False)
