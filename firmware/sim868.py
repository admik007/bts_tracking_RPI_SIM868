"""SIM868 GSM serving cell and GNSS reader, no GPRS data connection required."""
import time
from machine import UART, Pin
import config

class SIM868:
    def __init__(self):
        # Match the UART constructor used by the verified working Pico script.
        # RP2040 UART0 default pins are GP0 TX / GP1 RX.
        self.uart = UART(config.MODEM_UART, config.MODEM_BAUD)

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
        # Tested board wiring: request OFF with GP14 LOW for one second,
        # then request ON with GP14 HIGH and hold it HIGH.
        # Apply only once per application run, not on later retries.
        if not getattr(self, "_power_initialized", False):
            self.power_pin = Pin(getattr(config, "PWRKEY_PIN", 14),
                                 Pin.OUT, value=0)
            print("SIM868 power: LOW (1s)")
            self.power_pin.value(0)
            time.sleep(1)
            print("SIM868 power: HIGH")
            self.power_pin.value(1)
            self._power_initialized = True
            print("SIM868 GSM startup: waiting 12s")
            time.sleep(12)

        for attempt in range(8):
            response = self.command("AT", 2000)
            if "OK" in response:
                print("SIM868 AT OK")
                return self.initialize()
            print("SIM868 AT retry", attempt + 1, repr(response))
            time.sleep(1)
        return False

    def initialize(self):
        self.command("ATE0")
        print("SIM868 CPIN:", self.command("AT+CPIN?").strip())
        print("SIM868 CREG:", self.command("AT+CREG?").strip())
        print("SIM868 CGREG:", self.command("AT+CGREG?").strip())
        print("SIM868 COPS:", self.command("AT+COPS?").strip())
        print("SIM868 CENG enable:", self.command("AT+CENG=4,0", 3000).strip())
        print("SIM868 GNSS enable:", self.command("AT+CGNSPWR=1", 5000).strip())
        return True

    @staticmethod
    def _number(v, base=10):
        try:
            return int(v.strip().strip('"'), base)
        except (ValueError, TypeError):
            return None

    def cell(self):
        result = {"technology": "GSM", "mcc": None, "mnc": None,
                  "cellid": None, "lac": None, "bsic": None,
                  "csq": None, "creg": None, "cgreg": None}
        for line in self.command("AT+CSQ").splitlines():
            if line.startswith("+CSQ:"):
                csq = self._number(line.split(":", 1)[1].split(",")[0])
                result["csq"] = csq if csq is not None and csq != 99 else None
        for line in self.command("AT+CREG?").splitlines():
            if line.startswith("+CREG:"):
                parts = line.split(":", 1)[1].strip().split(",")
                if len(parts) >= 2:
                    result["creg"] = self._number(parts[1])
        for line in self.command("AT+CGREG?").splitlines():
            if line.startswith("+CGREG:"):
                parts = line.split(":", 1)[1].strip().split(",")
                if len(parts) >= 2:
                    result["cgreg"] = self._number(parts[1])
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
            cellid = self._number(fields[6], 16)
            lac = self._number(fields[9], 16)
            if mcc == "000" or mnc == "00" or not cellid:
                continue
            result["bsic"] = self._number(fields[5])
            result["cellid"] = cellid
            result["lac"] = lac
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
