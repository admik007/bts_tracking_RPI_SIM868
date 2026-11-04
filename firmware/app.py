"""BTS Tracking v1: independent measurement, serial JSON output, no SD/MQTT."""
import machine
import time
import ujson
import ubinascii
import config
from sim868 import SIM868

DEVICE_ID = ubinascii.hexlify(machine.unique_id()).decode()

def run():
    led = machine.Pin("LED", machine.Pin.OUT)
    sim = SIM868()
    print("BTS TRACKING v1, Pico:", DEVICE_ID)
    if not sim.start():
        print("SIM868 did not respond; retrying periodically")
    interval_ms = max(1000, int(config.SAMPLE_SECONDS * 1000))
    while True:
        start = time.ticks_ms()
        try:
            cell = sim.cell()
            gps = sim.gnss()
            record = {"device": DEVICE_ID, "source": "bts_pico_sim868"}
            record.update(cell)
            record.update(gps)
            # GSM identity is usable even with no GNSS fix or no data session.
            print("BTS_JSON:" + ujson.dumps(record))
            led.toggle()
            if cell["cellid"] is None and not sim.start():
                print("SIM868 reinit unsuccessful")
        except Exception as exc:
            print("Measurement error:", exc)
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        if elapsed < interval_ms:
            time.sleep_ms(interval_ms - elapsed)
