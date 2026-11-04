"""SIM868 GSM serving cell and GNSS reader, no GPRS data connection required."""
import time
from machine import UART, Pin
import config

class SIM868:
    def __init__(self):
        self.uart = UART(config.MODEM_UART, baudrate=config.MODEM_BAUD,
                         tx=Pin(config.MODEM_TX), rx=Pin(config.MODEM_RX),
                         timeout=100, rxbuf=2048)

    def command(self, cmd, timeout_ms=2000):
        while self.uart.any():
            self.uart.read()
        self.uart.write((cmd + "\r\n").encode())
        start = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    buf.extend(chunk)
                    if b"\r\nOK\r\n" in buf or b"\r\nERROR\r\n" in buf:
                        break
            time.sleep_ms(20)
        return bytes(buf).decode("utf-8", "ignore")

    def start(self):
        if getattr(config, "PULSE_PWRKEY_ON_BOOT", False):
            pin = Pin(config.PWRKEY_PIN, Pin.OUT)
            active = config.PWRKEY_ACTIVE_LEVEL
            pin.value(1 - active)
            time.sleep_ms(100)
            pin.value(active)
            time.sleep_ms(config.PWRKEY_PULSE_MS)
            pin.value(1 - active)
            time.sleep(6)
        for _ in range(3):
            if "OK" in self.command("AT"):
                self.command("ATE0")
                self.command("AT+CENG=4,0", 3000)
                self.command("AT+CGNSPWR=1", 5000)
                return True
            time.sleep(1)
        return False

    @staticmethod
    def _number(v, base=10):
        try:
            return int(v.strip().strip('"'), base)
        except (ValueError, TypeError):
            return None

    def cell(self):
        result = {"technology": "GSM", "mcc": None, "mnc": None,
                  "cellid": None, "lac": None, "bsic": None,
                  "csq": None, "creg": None}
        for line in self.command("AT+CSQ").splitlines():
            if line.startswith("+CSQ:"):
                csq = self._number(line.split(":", 1)[1].split(",")[0])
                result["csq"] = csq if csq is not None and csq != 99 else None
        for line in self.command("AT+CREG?").splitlines():
            if line.startswith("+CREG:"):
                parts = line.split(":", 1)[1].strip().split(",")
                if len(parts) >= 2:
                    result["creg"] = self._number(parts[1])
        for line in self.command("AT+CENG?", 3000).splitlines():
            if not line.startswith("+CENG: 0,"):
                continue
            # SIM868 mode 4: bcch,rxl,rxq,mcc,mnc,bsic,cellid,rla,txp,lac,...
            raw = line.split('"', 2)
            if len(raw) < 2:
                continue
            fields = raw[1].split(",")
            if len(fields) < 10:
                continue
            mcc, mnc = fields[3].strip(), fields[4].strip()
            if not (mcc.isdigit() and len(mcc) == 3 and mnc.isdigit()
                    and len(mnc) in (2, 3)):
                continue
            result["mcc"] = mcc
            result["mnc"] = mnc
            result["bsic"] = self._number(fields[5])
            result["cellid"] = self._number(fields[6], 16)
            result["lac"] = self._number(fields[9], 16)
            break
        return result

    def gnss(self):
        result = {"gps_valid": False, "time": None, "lat": None,
                  "lon": None, "alt": None, "speed_kmh": None,
                  "course": None, "sat": None}
        for line in self.command("AT+CGNSINF", 3000).splitlines():
            if not line.startswith("+CGNSINF:"):
                continue
            parts = line.split(":", 1)[1].strip().split(",")
            if len(parts) < 8 or parts[0].strip() != "1" or parts[1].strip() != "1":
                break
            try:
                raw_time = parts[2].strip()
                lat, lon = float(parts[3]), float(parts[4])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    break
                result["gps_valid"] = True
                result["lat"], result["lon"] = lat, lon
                result["alt"] = float(parts[5]) if parts[5] else None
                # CGNSINF speed is in km/h.
                result["speed_kmh"] = float(parts[6]) if parts[6] else None
                result["course"] = float(parts[7]) if parts[7] else None
                if len(raw_time) >= 14 and raw_time[:14].isdigit():
                    result["time"] = (raw_time[0:4] + "-" + raw_time[4:6] + "-" +
                                      raw_time[6:8] + "T" + raw_time[8:10] + ":" +
                                      raw_time[10:12] + ":" + raw_time[12:14] + "Z")
                if len(parts) > 14:
                    result["sat"] = self._number(parts[14])
            except (ValueError, IndexError):
                pass
            break
        return result
