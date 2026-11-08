"""BTS Tracking central AP receiver with SD-backed JSONL storage.

The unchanged main.py performs infrastructure Wi-Fi / OTA at boot; this app
switches to the open BTS-TRACKING AP and accepts JSON lines over TCP.
Each accepted record is appended to /sd/pending.jsonl before replying OK.
LCD status enabled; MQTT upload remains future work. No flash fallback: a failed SD write returns ERR sd.
"""
import network
import socket
import time
import ujson
import machine
import os
import config
import sdcard
import config_wifi
import mqtt_upload

try:
    from lcd import StatusLCD
except Exception as exc:
    StatusLCD = None
    print('LCD module unavailable:', exc)

AP_SSID = "BTS-TRACKING"
AP_IP = "192.168.4.1"
LISTEN_PORT = 5000
MAX_LINE_BYTES = 2048
SD_MOUNT = "/sd"
QUEUE_PATH = "/sd/pending.jsonl"
POS_SLOT_A = "/sd/bts.pos.a"
POS_SLOT_B = "/sd/bts.pos.b"
MQTT_TOPIC_PREFIX = getattr(config_wifi, "BTS_MQTT_TOPIC_PREFIX", "bts")
MQTT_HOST = getattr(config_wifi, "MQTT_HOST", None)
MQTT_PORT = getattr(config_wifi, "MQTT_PORT", 1883)
MQTT_USER = getattr(config_wifi, "MQTT_USER", None)
MQTT_PASS = getattr(config_wifi, "MQTT_PASS", None)
KEY0 = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
KEY2 = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
KEY3 = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)
# KEY1 GP17 is the SD-card CS pin: never initialize it as a key.


# Standard SPI0 wiring for an SD module; override in local config.py.
# NOTE: GP17 is also a button on some ST7735 LCD boards: do NOT share CS.
SD_SPI_ID = getattr(config, "SD_SPI_ID", 0)
SD_SCK_PIN = getattr(config, "SD_SCK_PIN", 18)
SD_MOSI_PIN = getattr(config, "SD_MOSI_PIN", 19)
SD_MISO_PIN = getattr(config, "SD_MISO_PIN", 16)
SD_CS_PIN = getattr(config, "SD_CS_PIN", 17)
SD_BAUDRATE = getattr(config, "SD_BAUDRATE", 10_000_000)

sd_ready = False
sd_fault = None
records_saved = 0
lcd = None
gps_cache = None
GPS_CACHE_MAX_AGE_MS = 60000
sender_cells = {}  # device -> (MCCMNC, CellID, last_seen_ms, previous_CellID)
MAX_LCD_SENDERS = 3
_sd_spi = None
_sd_device = None


def show_status(state="RECEIVING"):
    if lcd is None:
        return
    try:
        lcd.render(sd_ready, records_saved, sender_cells, state,
                   gps_cache_is_fresh())
    except Exception as exc:
        print("LCD update error:", exc)


def mount_sd():
    global sd_ready, sd_fault, _sd_spi, _sd_device
    # Follow the tested GPS Tracking logger startup sequence.
    for attempt in range(1, 4):
        print("SD init attempt {}/3".format(attempt))
        try:
            try:
                os.umount(SD_MOUNT)
            except OSError:
                pass
            _sd_spi = machine.SPI(
                SD_SPI_ID, baudrate=SD_BAUDRATE, polarity=0, phase=0,
                sck=machine.Pin(SD_SCK_PIN),
                mosi=machine.Pin(SD_MOSI_PIN),
                miso=machine.Pin(SD_MISO_PIN))
            cs = machine.Pin(SD_CS_PIN, machine.Pin.OUT, value=1)
            _sd_spi.write(b"\xff" * 10)
            time.sleep_ms(100)
            _sd_device = sdcard.SDCard(_sd_spi, cs)
            os.mount(os.VfsFat(_sd_device), SD_MOUNT)
            with open(QUEUE_PATH, "a") as out:
                pass
            _rotate_queue_if_needed()
            sd_ready = True
            sd_fault = None
            print("SD mounted:", SD_MOUNT)
            print("MQTT pending queue:", QUEUE_PATH)
            show_status("SD READY")
            return True
        except Exception as exc:
            sd_ready = False
            sd_fault = str(exc)
            print("SD ERROR (attempt {}): {}".format(attempt, sd_fault))
            show_status("SD ERROR")
            try:
                os.umount(SD_MOUNT)
            except OSError:
                pass
            try:
                cs.value(1)
            except (OSError, NameError):
                pass
            time.sleep_ms(500)
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
        # Rotate only after the complete JSONL record has been closed.
        try:
            _rotate_queue_if_needed()
        except Exception as rotate_exc:
            # The record is already safely stored. Retry rotation on next append.
            print("SD queue rotation deferred:", rotate_exc)
        return True
    except Exception as exc:
        sd_ready = False
        sd_fault = str(exc)
        print("SD ERROR (append):", sd_fault)
        show_status("SD WRITE ERROR")
        # Deliberately do not acknowledge this record.
        return False


def _valid_gps_record(record):
    valid = record.get("gps_valid") is True or record.get("gps_valid") == 1
    if not valid:
        return False
    try:
        lat = float(record.get("lat"))
        lon = float(record.get("lon"))
        return lat != 0 and lon != 0
    except (TypeError, ValueError):
        return False


def gps_cache_is_fresh():
    if gps_cache is None:
        return False
    age = time.ticks_diff(time.ticks_ms(), gps_cache["received_ms"])
    return 0 <= age <= GPS_CACHE_MAX_AGE_MS


def apply_gps_fallback(record):
    """Any sender with a live fix becomes master; other senders reuse it."""
    global gps_cache
    device = record.get("device")
    if _valid_gps_record(record):
        gps_cache = {
            "received_ms": time.ticks_ms(),
            "source": device,
            "time": record.get("time"),
            "lat": record.get("lat"),
            "lon": record.get("lon"),
            "alt": record.get("alt"),
            "speed_kmh": record.get("speed_kmh"),
            "course": record.get("course"),
            "sat": record.get("sat")
        }
        record["sender_gps_valid"] = True
        record["gps_source"] = device
        return record

    record["sender_gps_valid"] = False
    if gps_cache_is_fresh():
        for key in ("time", "lat", "lon", "alt", "speed_kmh", "course", "sat"):
            record[key] = gps_cache.get(key)
        record["gps_valid"] = True
        record["gps_source"] = gps_cache["source"]
    else:
        record["gps_valid"] = False
        record["gps_source"] = None
        record["lat"] = None
        record["lon"] = None
    return record


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
                    record = apply_gps_fallback(record)
                except (ValueError, TypeError, UnicodeError) as exc:
                    print("Invalid record:", exc)
                    client.send(b"ERR json\n")
                    continue
                if save_record(record):
                    device = record.get("device")
                    if device in sender_cells or len(sender_cells) < MAX_LCD_SENDERS:
                        operator = str(record.get("mcc", "")) + str(record.get("mnc", ""))
                        cellid = str(record.get("cellid", "-"))
                        old = sender_cells.get(device)
                        previous = "-"
                        if old is not None:
                            old_operator, old_cellid = old[:2]
                            # Never show a previous cell from a different network.
                            if old_operator == operator:
                                previous = old[3] if len(old) > 3 else "-"
                                if cellid not in ("", "-", "None") and old_cellid != cellid:
                                    if old_cellid not in ("", "-", "None"):
                                        previous = old_cellid
                                        print("CELL CHANGE: {} {} -> {} (device {})".format(
                                            operator, old_cellid, cellid, device))
                        # GPS fix is shared dynamically between all senders.
                        sender_cells[device] = (
                            operator, cellid, time.ticks_ms(), previous)
                    print("SD SAVED #{}: {}".format(records_saved, ujson.dumps(record)))
                    show_status("RECEIVING")
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


def _key_pressed(pin):
    # Active-low keys, debounced. A pressed-and-held key is detected too.
    if pin.value() != 0:
        return False
    time.sleep_ms(35)
    return pin.value() == 0


def _request_during_upload():
    if _key_pressed(KEY3):
        return "SAFE"
    if _key_pressed(KEY2):
        return "RECEIVING"
    return None


ARCHIVE_PREFIX = "bts_"
ARCHIVE_SUFFIX = ".jsonl"
MAX_QUEUE_FILE_BYTES = 2_000_000


def _archive_ids():
    ids = []
    try:
        names = os.listdir(SD_MOUNT)
    except OSError:
        return ids
    for name in names:
        if (name.startswith(ARCHIVE_PREFIX) and
                name.endswith(ARCHIVE_SUFFIX) and len(name) == 16):
            try:
                ids.append(int(name[4:10]))
            except ValueError:
                pass
    ids.sort()
    return ids


def _queue_files():
    # Archived files are immutable; pending.jsonl is always the newest file.
    files = []
    for file_id in _archive_ids():
        files.append((file_id, SD_MOUNT + "/" + ARCHIVE_PREFIX +
                      "{:06d}".format(file_id) + ARCHIVE_SUFFIX))
    files.append((files[-1][0] + 1 if files else 1, QUEUE_PATH))
    return files


def _rotate_queue_if_needed():
    size = os.stat(QUEUE_PATH)[6]
    if size < MAX_QUEUE_FILE_BYTES:
        return False
    ids = _archive_ids()
    next_id = ids[-1] + 1 if ids else 1
    archive_path = SD_MOUNT + "/" + ARCHIVE_PREFIX + "{:06d}".format(next_id) + ARCHIVE_SUFFIX
    os.rename(QUEUE_PATH, archive_path)
    with open(QUEUE_PATH, "a") as out:
        pass
    print("SD queue rotated:", archive_path, "bytes:", size)
    return True


def _cursor_checksum(file_id, pos):
    # Include both file number and byte offset to detect torn cursor writes.
    return ((file_id * 0x45D9F3B) ^ pos ^ 0x5A5A5A5A) & 0xFFFFFFFF


def _queue_path_for_id(file_id):
    for current_id, path in _queue_files():
        if current_id == file_id:
            return path
    return None


def _read_position(path):
    try:
        with open(path, "r") as f:
            fields = f.read(48).strip().split(":")
        # Legacy format: offset:checksum for the original pending.jsonl.
        if len(fields) == 2:
            file_id = 1
            pos = int(fields[0])
            checksum_ok = int(fields[1], 16) == ((pos ^ 0x5A5A5A5A) & 0xFFFFFFFF)
        elif len(fields) == 3:
            file_id = int(fields[0])
            pos = int(fields[1])
            checksum_ok = int(fields[2], 16) == _cursor_checksum(file_id, pos)
        else:
            return None
        queue_path = _queue_path_for_id(file_id)
        if not checksum_ok or queue_path is None or pos < 0:
            return None
        if pos > os.stat(queue_path)[6]:
            return None
        return (file_id, pos)
    except (OSError, ValueError, IndexError):
        return None


def _load_cursor():
    a = _read_position(POS_SLOT_A)
    b = _read_position(POS_SLOT_B)
    if a is None and b is None:
        return (1, 0), POS_SLOT_A
    if b is None or (a is not None and a >= b):
        return a, POS_SLOT_B
    return b, POS_SLOT_A


def _commit_cursor(file_id, pos, next_slot):
    # Two alternating slots: a torn write leaves the previous slot intact.
    with open(next_slot, "w") as f:
        f.write("{}:{}:{:08x}\n".format(
            file_id, pos, _cursor_checksum(file_id, pos)))
        f.flush()
    return POS_SLOT_B if next_slot == POS_SLOT_A else POS_SLOT_A


def _pending_bytes(cursor):
    cursor_id, cursor_pos = cursor
    total = 0
    for file_id, path in _queue_files():
        if file_id < cursor_id:
            continue
        size = os.stat(path)[6]
        total += max(0, size - (cursor_pos if file_id == cursor_id else 0))
    return total


def _stop_access_point(ap, server):
    try:
        server.close()
    except OSError:
        pass
    ap.active(False)
    print("Receiver AP stopped")


def _connect_home_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        return sta, None
    for attempt in range(2):
        print("Home Wi-Fi attempt", attempt + 1)
        try:
            sta.connect(config_wifi.SSID, config_wifi.PASS)
        except OSError as exc:
            print("Wi-Fi connect error:", exc)
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 7000:
            action = _request_during_upload()
            if action:
                return sta, action
            if sta.isconnected():
                print("Home Wi-Fi connected:", sta.ifconfig()[0])
                return sta, None
            time.sleep_ms(100)
        try:
            sta.disconnect()
        except OSError:
            pass
    raise OSError("Home Wi-Fi unavailable")


def _disconnect_home_wifi(sta):
    if sta is None:
        return
    try:
        sta.disconnect()
    except OSError:
        pass
    sta.active(False)


def _upload_pending(sta):
    if not sd_ready:
        raise OSError("SD unavailable")
    if not MQTT_HOST:
        raise ValueError("MQTT_HOST missing in local config_wifi.py")
    cursor, next_slot = _load_cursor()
    pending_bytes = _pending_bytes(cursor)
    sent = 0
    print("MQTT pending bytes:", pending_bytes,
          "resume file:", cursor[0], "offset:", cursor[1])
    show_status("SENT: 0")
    client_id = "bts-receiver-" + "".join("{:02x}".format(b) for b in machine.unique_id())
    client = mqtt_upload.MQTTUploader(
        MQTT_HOST, MQTT_PORT, client_id, MQTT_USER, MQTT_PASS)
    try:
        client.connect()
        print("MQTT connected:", MQTT_HOST, MQTT_PORT)
        for file_id, path in _queue_files():
            if file_id < cursor[0]:
                continue
            pos = cursor[1] if file_id == cursor[0] else 0
            with open(path, "rb") as f:
                f.seek(pos)
                while True:
                    action = _request_during_upload()
                    if action:
                        return action, sent
                    line = f.readline()
                    if not line:
                        break
                    new_pos = f.tell()
                    if not line.endswith(b"\n"):
                        raise ValueError("Incomplete JSONL record at {}:{}".format(
                            file_id, pos))
                    record = ujson.loads(line.decode('utf-8'))
                    if not isinstance(record, dict) or not record.get("device"):
                        raise ValueError("Invalid JSONL record at {}:{}".format(
                            file_id, pos))
                    topic = "{}/{}/location".format(
                        MQTT_TOPIC_PREFIX, record["device"])
                    client.publish(topic, line.decode("utf-8").strip())
                    next_slot = _commit_cursor(file_id, new_pos, next_slot)
                    pos = new_pos
                    sent += 1
                    show_status("SENT: {}".format(sent))
                    if sent % 20 == 0:
                        print("MQTT uploaded:", sent, "file:", file_id,
                              "cursor:", pos)
        show_status("SENT: {}".format(sent))
        print("Upload complete; records:", sent)
        return None, sent
    finally:
        client.close()


def _safe_shutdown(ap=None, server=None, sta=None):
    global sd_ready
    if server is not None:
        try:
            server.close()
        except OSError:
            pass
    if ap is not None:
        ap.active(False)
    _disconnect_home_wifi(sta)
    if sd_ready:
        try:
            os.umount(SD_MOUNT)
            sd_ready = False
            print("SD unmounted - safe to power off")
        except OSError as exc:
            print("SD unmount FAILED:", exc)
            show_status("SD UNMOUNT ERR")
            return False
    show_status("SAFE TO OFF")
    return True


def _open_listener():
    ap = start_ap()
    address = socket.getaddrinfo("0.0.0.0", LISTEN_PORT)[0][-1]
    server = socket.socket()
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(address)
        server.listen(4)
        server.settimeout(0.2)
    except Exception:
        server.close()
        ap.active(False)
        raise
    print("Receiver listening on", AP_IP, "port", LISTEN_PORT)
    show_status("RECEIVING")
    return ap, server


def run():
    global lcd
    led = machine.Pin("LED", machine.Pin.OUT)
    if StatusLCD is not None:
        try:
            lcd = StatusLCD()
            print("LCD initialized (ST7735 128x128)")
        except Exception as exc:
            lcd = None
            print("LCD init failed:", exc)
    mount_sd()
    ap, server = _open_listener()
    sta = None
    mode = "RECEIVING"
    last_key = None
    last_lcd_refresh = time.ticks_ms()

    while True:
        # Refresh sender activity even when no messages arrive; otherwise
        # a disconnected sender would stay green indefinitely.
        if (mode == "RECEIVING" and
                time.ticks_diff(time.ticks_ms(), last_lcd_refresh) >= 1000):
            show_status("RECEIVING")
            last_lcd_refresh = time.ticks_ms()
        # Detect key-down edge, with release before the same key triggers again.
        pressed = None
        for name, pin in (("SAFE", KEY3), ("RECEIVING", KEY2), ("UPLOAD", KEY0)):
            if pin.value() == 0:
                pressed = name
                break
        if pressed != last_key and pressed is not None:
            time.sleep_ms(35)
            if (pressed == "SAFE" and KEY3.value() == 0 or
                pressed == "RECEIVING" and KEY2.value() == 0 or
                pressed == "UPLOAD" and KEY0.value() == 0):
                if pressed == "SAFE":
                    print("KEY3: safe power off")
                    if mode == "RECEIVING":
                        _stop_access_point(ap, server)
                        ap, server = None, None
                    if _safe_shutdown(ap, server, sta):
                        mode = "SAFE"
                    else:
                        mode = "ERROR"
                elif pressed == "RECEIVING" and mode != "RECEIVING":
                    print("KEY2: resume receiving")
                    _disconnect_home_wifi(sta)
                    sta = None
                    if not sd_ready and not mount_sd():
                        print("KEY2: SD remount failed; staying safe")
                        show_status("SD REMOUNT ERR")
                        mode = "SAFE"
                    else:
                        try:
                            ap, server = _open_listener()
                            mode = "RECEIVING"
                            print("KEY2: AP and TCP receiving restored")
                        except Exception as exc:
                            print("KEY2: AP restore failed:", exc)
                            mode = "ERROR"
                            show_status("AP RESTART ERR")
                elif pressed == "UPLOAD" and mode in ("RECEIVING", "UPLOADING"):
                    print("KEY0: upload pending MQTT records")
                    if mode == "RECEIVING":
                        _stop_access_point(ap, server)
                        ap, server = None, None
                    mode = "UPLOADING"
                    show_status("WIFI CONNECT")
                    try:
                        sta, action = _connect_home_wifi()
                        if action is None:
                            show_status("MQTT UPLOAD")
                            action, sent = _upload_pending(sta)
                        if action == "SAFE":
                            if _safe_shutdown(sta=sta):
                                mode = "SAFE"
                            else:
                                mode = "ERROR"
                        elif action == "RECEIVING":
                            _disconnect_home_wifi(sta)
                            sta = None
                            if not sd_ready and not mount_sd():
                                mode = "ERROR"
                                show_status("SD REMOUNT ERR")
                            else:
                                ap, server = _open_listener()
                                mode = "RECEIVING"
                                print("KEY2: AP and TCP receiving restored")
                        else:
                            show_status("UPLOAD DONE")
                    except Exception as exc:
                        print("Upload error:", exc)
                        show_status("UPLOAD ERROR")
        last_key = pressed

        if mode == "RECEIVING":
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
        else:
            time.sleep_ms(100)
