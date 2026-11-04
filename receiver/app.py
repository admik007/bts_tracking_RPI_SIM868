"""BTS Tracking - central Pico W AP receiver (phase 1: console only).

Boot order is controlled by the existing firmware/main.py:
  1. Try infrastructure Wi-Fi and OTA by DEVICE_ID.
  2. Import app and call run() regardless of Wi-Fi availability.
  3. This app disables STA, starts AP and receives newline-delimited JSON.

No SD writes, MQTT uploads or LCD yet.
"""
import network
import socket
import time
import ujson
import machine

AP_SSID = "BTS-TRACKING"
AP_IP = "192.168.4.1"
LISTEN_PORT = 5000
MAX_LINE_BYTES = 2048


def start_ap():
    # The existing main.py may have connected to home Wi-Fi for OTA.
    sta = network.WLAN(network.STA_IF)
    try:
        sta.disconnect()
    except OSError:
        pass
    sta.active(False)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID)

    # Pico W commonly defaults to 192.168.4.1, but set it explicitly.
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
                # Idle/disconnected sender. Return to accept loop.
                break
            if not chunk:
                break
            pending += chunk
            if len(pending) > MAX_LINE_BYTES:
                print("Rejected oversized message:", address)
                client.send(b"ERR size\n")
                break

            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    record = parse_record(line)
                    print("BTS_JSON:" + ujson.dumps(record))
                    # ACK only after successful parsing and console output.
                    # Future SD implementation must ACK only after durable write.
                    client.send(b"OK\n")
                except (ValueError, TypeError, UnicodeError) as exc:
                    print("Invalid record:", exc)
                    client.send(b"ERR json\n")
    finally:
        client.close()
        print("Disconnected:", address)


def run():
    led = machine.Pin("LED", machine.Pin.OUT)
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
