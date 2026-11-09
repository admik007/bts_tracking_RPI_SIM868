"""SIM868 GSM serving cell and GNSS reader, no GPRS data connection required."""
import time
from machine import UART, Pin
import config

class SIM868:
    def __init__(self, wdt=None):
        self.wdt = wdt
        # Match the UART constructor used by the verified working Pico script.
        # RP2040 UART0 default pins are GP0 TX / GP1 RX.
        self.uart = UART(config.MODEM_UART, config.MODEM_BAUD)

    def _feed_wdt(self):
        if self.wdt is not None:
            self.wdt.feed()

    def _sleep_ms(self, duration_ms):
        remaining = int(duration_ms)
        while remaining > 0:
            self._feed_wdt()
            chunk = min(1000, remaining)
            time.sleep_ms(chunk)
            remaining -= chunk
        self._feed_wdt()

    def command(self, cmd, timeout_ms=2000):
        while self.uart.any():
            self._feed_wdt()
            self.uart.read()
        self.uart.write((cmd + "\r\n").encode())
        start = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            self._feed_wdt()
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    buf.extend(chunk)
                    if b"\r\nOK\r\n" in buf or b"\r\nERROR\r\n" in buf:
                        break
            self._sleep_ms(20)
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
            self._sleep_ms(1000)
            print("SIM868 power: HIGH")
            self.power_pin.value(1)
            self._power_initialized = True
            print("SIM868 GSM startup: waiting 12s")
            self._sleep_ms(12000)

        for attempt in range(8):
            response = self.command("AT", 2000)
            if "OK" in response:
                print("SIM868 AT OK")
                return self.initialize()
            print("SIM868 AT retry", attempt + 1, repr(response))
            self._sleep_ms(1000)
        return False

    def initialize(self):
        self.command("ATE0")
        print("SIM868 CPIN:", self.command("AT+CPIN?").strip())
        print("SIM868 CREG:", self.command("AT+CREG?").strip())
        print("SIM868 CGREG:", self.command("AT+CGREG?").strip())
        print("SIM868 COPS:", self.command("AT+COPS?").strip())
        print("SIM868 CENG enable:", self.command("AT+CENG=4,0", 3000).strip())
        print("SIM868 GNSS power:", self.command("AT+CGNSPWR=1", 5000).strip())
        return True

    @staticmethod
    def _number(v, base=10):
        try:
            return int(v.strip().strip('"'), base)
        except (ValueError, TypeError):
            return None

    def gnss(self):
        """Return the current SIM868 GNSS fix, or an explicitly invalid fix."""
        result = {"gps_valid": False, "time": None, "lat": None,
                  "lon": None, "alt": None, "speed_kmh": None,
                  "course": None, "sat": None}
        response = self.command("AT+CGNSINF", 3000)
        for line in response.splitlines():
            if not line.startswith("+CGNSINF:"):
                continue
            fields = line.split(":", 1)[1].strip().split(",")
            if len(fields) < 8 or fields[1].strip() != "1":
                break
            try:
                lat = float(fields[3])
                lon = float(fields[4])
                if lat == 0 or lon == 0:
                    break
                stamp = fields[2].strip()
                gps_time = None
                if len(stamp) >= 14:
                    gps_time = "{}-{}-{}T{}:{}:{}Z".format(
                        stamp[0:4], stamp[4:6], stamp[6:8],
                        stamp[8:10], stamp[10:12], stamp[12:14])
                result["gps_valid"] = True
                result["time"] = gps_time
                result["lat"] = lat
                result["lon"] = lon
                result["alt"] = float(fields[5]) if fields[5] else None
                result["speed_kmh"] = float(fields[6]) if fields[6] else None
                result["course"] = float(fields[7]) if fields[7] else None
                # SIM868 CGNSINF satellite-count fields vary by firmware;
                # field 15 is GNSS satellites used on standard responses.
                if len(fields) > 15 and fields[15]:
                    result["sat"] = int(float(fields[15]))
            except (ValueError, IndexError):
                pass
            break
        return result

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
