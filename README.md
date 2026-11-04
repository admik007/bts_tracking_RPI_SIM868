# BTS Tracking – Pico W / SIM868 firmware v1

**Purpose:** three Pico W (Orange, O2, 4ka), each with SIM868, independently collecting serving GSM cell identity and integrated GNSS fix. Telekom is collected by the existing GPS tracker. Firmware **does not** publish MQTT, write SD, or change server DB yet; every sample is a JSON line prefixed `BTS_JSON:` on USB serial.

## Connections

- SIM868 UART TX -> Pico GP1 (RX), SIM868 UART RX -> Pico GP0 (TX), common GND; **use compatible 3.3 V logic**.
- UART0 at 115200 baud, configurable.
- SIM868 requires its own power supply with sufficient peak current; **do not power it from Pico 3.3 V**.
- GPS antenna to SIM868 GNSS antenna input. GNSS fix can take time outdoors.
- Optional PWRKEY via GP14 is **disabled by default**, because trigger polarity/timing depends on the carrier board. Enable only after verifying hardware wiring.

## Installation

1. Install MicroPython on Pico W / Pico 2 W; open in Thonny.
2. Copy `firmware/config.py.example` to `config.py` **on the Pico** and set Wi-Fi/OTA server. Keep real secrets out of Git.
3. Copy `main.py`, `app.py`, `sim868.py`, `config.py` to Pico filesystem.
4. Restart and watch USB serial. Expected `BTS_JSON:{...}` roughly every 5 seconds (AT command time may extend that interval).
5. Verify `mcc`, `mnc`, `cellid`, `lac`, `bsic` against raw `AT+CENG?` and `gps_valid` outdoors. If `mcc/mnc` differ from SIM operator, the modem may be roaming.

## OTA hosting

`main.py` checks `OTA_BASE_URL/manifest.json` if Wi-Fi connects within ~14 seconds; otherwise runs local `app.py`. It never waits for Internet to collect measurements. Host e.g. `http://192.168.10.1/firmware/bts/` with files `app.py`, `sim868.py`, `manifest.json`.

Manifest example (replace placeholders with SHA256 digests of **exact hosted bytes**):

```json
{"version":"1", "files":{"app.py":"<64 hex sha256>","sim868.py":"<64 hex sha256>"}}
```

Linux digest command: `sha256sum app.py sim868.py`.

OTA verifies SHA-256 before switching. `main.py` and `config.py` are protected from OTA. **Important:** OTA over HTTP is not authenticated; SHA-256 only verifies the downloaded bytes against the manifest, which can itself be modified by an attacker on the network. Use only on a trusted isolated AP and move to authenticated HTTPS/signatures before untrusted networks. No rollback after a successfully installed but logically broken application; keep USB/Thonny recovery available.

## Important limitations

- No SD and no MQTT: data are **not retained** after serial output. Network drop does not stop BTS reading.
- SIM868 is a 2G GSM module; it does **not** measure LTE/5G cells.
- Each Pico reports its own GNSS location only if GNSS returns a fix; without a fix lat/lon are null.
- GNSS on/off and `+CENG` details should be validated on the actual SIM868 breakout and firmware revision.
- One SIM868 measures its **serving GSM cell**, not a complete map of neighboring sectors.
