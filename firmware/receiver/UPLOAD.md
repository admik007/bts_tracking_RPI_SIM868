# BTS Receiver buttons and MQTT upload

## Buttons (active-low with internal pull-ups)

| Key | GPIO | Purpose |
| --- | --- | --- |
| KEY0 | GP15 | Switch from receiving to home Wi-Fi and upload via MQTT |
| KEY1 | GP17 | **UNUSED**; shared with SD CS |
| KEY2 | GP2 | Stop upload / reconnect AP / resume receiving |
| KEY3 | GP3 | Stop upload and safely unmount SD before power off |

Buttons are polled from the main loop without a second thread.
A key pressed during a network call can take up to the network socket
timeout (5 seconds) to respond. Holding the button until it responds
is recommended. No firmware update is triggered when switching modes.

## MQTT setup

On the **receiver Pico only**, extend local `config_wifi.py` (NOT the
repository example; the bootloader protects this local config from OTA):

```python
# Existing OTA home Wi-Fi config stays in place:
SSID = "your-home-ssid"
PASS = "your-home-wifi-password"
HOST = "bts.ztk-comp.sk"  # Existing OTA HTTP host, unchanged

# New MQTT broker settings (use the broker actually reachable over Wi-Fi):
MQTT_HOST = "your-mqtt-broker-host"
MQTT_PORT = 1883
MQTT_USER = "your-mqtt-username"   # Omit if anonymous broker
MQTT_PASS = "your-mqtt-password"   # Omit if anonymous broker
BTS_MQTT_TOPIC_PREFIX = "bts"
```

Do not store real passwords in Git. MQTT here is **plain TCP**, not TLS.
Use a trusted home LAN or secured broker connection.

Each sender record is published unchanged using MQTT 3.1.1 QoS 1 to:
`bts/<sender-device-id>/location`. The server must separately
subscribe to this topic and handle BTS record ingestion. The existing
GPS Tracking subscription/topic is not modified.

## SD queue and restart recovery

Receiver logs BTS measurements as JSONL in `/sd/pending.jsonl`.
KEY0 stops the AP listener before sending. No sender buffers are changed.

After each broker PUBACK, the receiver writes a byte-offset cursor
to alternating SD files `/sd/bts.pos.a` and `/sd/bts.pos.b`
(with checksum), preserving the previous valid offset if the new cursor
write is interrupted.

On a future upload it resumes from the highest valid cursor. If the
MQTT transfer succeeds but power fails before recording the cursor,
**that record may be sent again**. QoS 1 / PUBACK is not a server
database commit; deduplication on the ingestion server is recommended.

The JSONL file is deliberately **retained**, even after successful
upload. It is an audit/archive log until a safe compaction/cleanup
procedure is designed. Do not manually truncate it while a receiver is
running; a shorter file can invalidate saved offsets.

If Wi-Fi/MQTT upload fails, the receiver stays out of AP mode and shows
`UPLOAD ERROR`. KEY0 retries, KEY2 restarts the AP, KEY3 safe-unmounts
the SD. If Wi-Fi is unavailable, no records are deleted.

KEY3 stops reception, closes the listener, disconnects Wi-Fi and unmounts
`/sd`; the LCD then shows `SAFE TO OFF`. The Pico itself stays powered.
KEY2 from this state remounts SD and restarts the BTS AP.

## LCD

The display shows `RECEIVING`, `WIFI CONNECT`, `SENT: N`,
`UPLOAD DONE`, `UPLOAD ERROR`, or `SAFE TO OFF` and keeps the
last three sender MCC/MNC + CellID rows. Number `SENT` is the number
of successfully acknowledged records during the current upload run.

No extra MQTT Python library needs to be installed: `mqtt_upload.py`
is included in the OTA manifest.
