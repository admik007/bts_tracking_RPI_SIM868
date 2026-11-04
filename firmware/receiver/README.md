# Receiver – SD queue (phase 2)

The existing `firmware/main.py` is unchanged. It attempts home Wi-Fi and OTA
at boot, then runs the receiver `app.py`. All receiver files are published by
the current Apache Alias directly from `firmware/receiver/`.

## Receiver SD card

Requires a **FAT/FAT32-formatted** microSD card connected over SPI. The
`sdcard.py` driver is delivered by OTA together with `app.py`
(original MicroPython driver from `micropython/micropython-lib`).

Defaults (SPI0), verified against `gps_tracking_RPI_SIM868/firmware/logger.py` and `just_mount.py`:

| Signal | Pico pin |
| --- | --- |
| MISO | GP16 |
| CS | GP17 |
| SCK | GP18 |
| MOSI | GP19 |
| Power | 3.3 V-compatible SD module; common GND |

**Hardware conflict:** GP17 is a key/button on some 1.44-inch ST7735 LCD
boards. If you use that board, connect the SD module CS to a different free
GPIO and set `SD_CS_PIN` accordingly. Never connect two active peripherals
to the same GPIO.

To override, add these values to the receiver's local `config.py`
(`main.py` intentionally protects this file from OTA):

```python
SD_SPI_ID = 0
SD_MISO_PIN = 16
SD_SCK_PIN = 18
SD_MOSI_PIN = 19
SD_CS_PIN = 17  # Change to the actual free GPIO used by your SD module
SD_BAUDRATE = 10000000
```

## Data and acknowledgements

On boot, the receiver mounts `/sd` and creates `/sd/pending.jsonl` if
necessary, without erasing existing data. Every TCP JSON record is written
as **one JSON object per line**. The queue is suitable for sequential MQTT
publishing later; records without GPS fix can still be saved and their
`time` field may be null.

The receiver answers `OK\n` **only if the file write and close succeed**.
If the SD is missing or an append fails, the receiver answers `ERR sd\n`
and prints an `SD ERROR` diagnostic. There is no flash fallback, sender
buffer or recovery mechanism yet; reinsert/repair the SD and restart
the receiver to remount it.

The TCP AP remains active even without the SD card. The next phase will
display `sd_ready` / `sd_fault` on the LCD and add MQTT upload.

## Quick verification

Watch USB/Thonny serial on the receiver:

```text
SD mounted: /sd
MQTT pending queue: /sd/pending.jsonl
Receiver listening on 192.168.4.1 port 5000
SD SAVED #1: {...}
```

Inspect with MicroPython REPL when the receiver is stopped:

```python
import os
print(os.listdir("/sd"))
with open("/sd/pending.jsonl") as f:
    print(f.readline())
```

**Power loss caution:** closing the file reduces the exposure, but sudden
power loss during SD/FAT writes can still damage the filesystem. Later
implement a safe power-off sequence through the LCD buttons.
