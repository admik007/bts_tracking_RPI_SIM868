"""Small MQTT 3.1.1 QoS1 publisher over Wi-Fi TCP (port 1883).

No additional MicroPython packages are required. publish() returns only
after a matching broker PUBACK (not a database/application confirmation).
"""
import socket


def _mqtt_string(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return bytes((len(value) >> 8, len(value) & 255)) + value


def _remaining_length(length):
    out = bytearray()
    while True:
        b = length % 128
        length //= 128
        out.append(b | (128 if length else 0))
        if not length:
            return out


def _read_exact(sock, count):
    result = bytearray()
    while len(result) < count:
        part = sock.recv(count - len(result))
        if not part:
            raise OSError("MQTT connection closed")
        result.extend(part)
    return bytes(result)


def _read_packet(sock):
    fixed = _read_exact(sock, 1)[0]
    mult = 1
    length = 0
    for _ in range(4):
        digit = _read_exact(sock, 1)[0]
        length += (digit & 127) * mult
        if not (digit & 128):
            return fixed, _read_exact(sock, length)
        mult *= 128
    raise OSError("Invalid MQTT remaining length")


class MQTTUploader:
    def __init__(self, host, port, client_id, user=None, password=None):
        self.host = host
        self.port = int(port)
        self.client_id = client_id
        self.user = user
        self.password = password
        self.sock = None
        self.packet_id = 0

    def connect(self):
        addr = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)[0][-1]
        sock = socket.socket()
        sock.settimeout(5)
        try:
            sock.connect(addr)
            flags = 0x02  # Clean session
            payload = _mqtt_string(self.client_id)
            if self.user is not None:
                flags |= 0x80
                if self.password is not None:
                    flags |= 0x40
                payload += _mqtt_string(self.user)
                if self.password is not None:
                    payload += _mqtt_string(self.password)
            variable = b"\x00\x04MQTT\x04" + bytes((flags, 0, 45))
            packet = b"\x10" + _remaining_length(len(variable) + len(payload)) + variable + payload
            sock.write(packet)
            typ, reply = _read_packet(sock)
            if typ != 0x20 or len(reply) != 2 or reply[1] != 0:
                raise OSError("MQTT CONNACK rejected: {}".format(reply))
            self.sock = sock
        except Exception:
            sock.close()
            raise

    def publish(self, topic, payload):
        if self.sock is None:
            raise OSError("MQTT not connected")
        self.packet_id = (self.packet_id % 65535) + 1
        identifier = self.packet_id.to_bytes(2, "big")
        body = _mqtt_string(topic) + identifier + payload.encode("utf-8")
        packet = b"\x32" + _remaining_length(len(body)) + body  # QoS 1 PUBLISH
        self.sock.write(packet)
        typ, reply = _read_packet(self.sock)
        if typ != 0x40 or reply != identifier:
            raise OSError("Expected matching MQTT PUBACK")

    def close(self):
        if self.sock is not None:
            try:
                self.sock.write(b"\xe0\x00")
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
