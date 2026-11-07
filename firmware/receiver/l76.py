"""L76/L76B GNSS receiver for the BTS tracking central Pico.
UART1: TX=GP4, RX=GP5, 9600 baud. Reads NMEA without blocking.
"""
from machine import UART, Pin
import time


class L76GPS:
    def __init__(self, uart_id=1, baudrate=9600, tx_pin=4, rx_pin=5):
        self.uart = UART(
            uart_id, baudrate=baudrate,
            tx=Pin(tx_pin), rx=Pin(rx_pin),
            timeout=0, rxbuf=2048
        )
        self.buffer = b""
        self.point = {
            "time": None, "lat": None, "lon": None,
            "alt": None, "speed_kmh": None, "course": None,
            "sat": None
        }
        self.last_fix_ms = None
        self.rmc_valid = False

    @staticmethod
    def _coordinate(value, direction):
        if not value or not direction:
            return None
        raw = float(value)
        degrees = int(raw / 100)
        minutes = raw - degrees * 100
        result = degrees + minutes / 60
        if direction in ("S", "W"):
            result = -result
        return round(result, 6)

    @staticmethod
    def _utc_datetime(date_value, time_value):
        if len(date_value) != 6 or len(time_value) < 6:
            return None
        day = int(date_value[0:2])
        month = int(date_value[2:4])
        year2 = int(date_value[4:6])
        year = 2000 + year2 if year2 < 80 else 1900 + year2
        hour = int(time_value[0:2])
        minute = int(time_value[2:4])
        second = int(float(time_value[4:]))
        return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
            year, month, day, hour, minute, second
        )

    def update(self):
        if self.uart.any():
            data = self.uart.read()
            if data:
                self.buffer += data
                if len(self.buffer) > 4096:
                    self.buffer = self.buffer[-2048:]
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            try:
                line = raw.decode().strip()
            except Exception:
                continue
            if line.startswith("$GNRMC") or line.startswith("$GPRMC"):
                self._parse_rmc(line)
            elif line.startswith("$GNGGA") or line.startswith("$GPGGA"):
                self._parse_gga(line)

    def _parse_rmc(self, line):
        fields = line.split("*", 1)[0].split(",")
        if len(fields) < 10:
            return
        self.rmc_valid = fields[2] == "A"
        if not self.rmc_valid:
            self.last_fix_ms = None
            return
        try:
            lat = self._coordinate(fields[3], fields[4])
            lon = self._coordinate(fields[5], fields[6])
            if lat is None or lon is None:
                return
            self.point["lat"] = lat
            self.point["lon"] = lon
            self.point["time"] = self._utc_datetime(fields[9], fields[1])
            self.point["speed_kmh"] = (
                round(float(fields[7]) * 1.852, 2) if fields[7] else None
            )
            self.point["course"] = float(fields[8]) if fields[8] else None
            self.last_fix_ms = time.ticks_ms()
        except (ValueError, IndexError):
            return

    def _parse_gga(self, line):
        fields = line.split("*", 1)[0].split(",")
        if len(fields) < 10:
            return
        try:
            quality = int(fields[6]) if fields[6] else 0
            self.point["sat"] = int(fields[7]) if fields[7] else 0
            self.point["alt"] = float(fields[9]) if fields[9] else None
            if quality == 0 and self.last_fix_ms is None:
                self.rmc_valid = False
        except (ValueError, IndexError):
            pass

    def has_fix(self):
        return (
            self.rmc_valid and self.last_fix_ms is not None and
            0 <= time.ticks_diff(time.ticks_ms(), self.last_fix_ms) <= 5000
        )

    def snapshot(self):
        valid = self.has_fix()
        return {
            "gps_valid": valid,
            "time": self.point["time"] if valid else None,
            "lat": self.point["lat"] if valid else None,
            "lon": self.point["lon"] if valid else None,
            "alt": self.point["alt"] if valid else None,
            "speed_kmh": self.point["speed_kmh"] if valid else None,
            "course": self.point["course"] if valid else None,
            "sat": self.point["sat"] if valid else None
        }
