# BTS receiver LCD – ST7735 1.44 inch (128x128)

Uses the original display driver from the older BTS Pico receiver, separated
into `lcd.py`. The receiver is still an AP/TCP listener, and writes every
accepted BTS JSON record to `/sd/pending.jsonl`.

## GPIO layout

| Peripheral | Pins |
| --- | --- |
| LCD SPI1 SCK/MOSI | GP10 / GP11 |
| LCD DC / CS / RESET | GP8 / GP9 / GP12 |
| LCD backlight PWM | GP13 |
| SD SPI0 MISO / SCK / MOSI | GP16 / GP18 / GP19 |
| SD CS | GP17 |

Important: the **button originally wired to GP17 shares the SD CS pin**.
KEY1 / GP17 is never initialized or read because it is SD CS.
KEY0 / GP15 starts upload, KEY2 / GP2 resumes receiving, and
KEY3 / GP3 safely unmounts SD. LCD display itself uses no SD GPIO.

## Display

- BTS TRACKING
- AP IP and TCP listener port
- SD OK / ERROR
- Count of stored messages during current run
- Up to three sender rows: sender number, MCC+MNC and CellID (without LAC)
- Last state (`RECEIVING`, `SD ERROR`)

The LCD is optional at runtime: if initialization fails, the receiver
continues to collect and store data, and prints an error to serial.
The display initializes before SD, so SD initialization errors are visible.

After merging and `git pull` on the Apache host, the receiver OTA manifest
updates `app.py`, `lcd.py` and `sdcard.py`. No changes to publisher or
bootstrap `main.py`. For keys and MQTT upload, see `UPLOAD.md`.

Sender rows are assigned in order of first successfully stored message during
this boot, and each device's row updates independently. Additional senders are
still logged to SD, but are not shown on this three-row screen. Row numbering
is local to the current boot, not a permanent device assignment.

Each sender's first row also shows a **G** directly before the
existing activity ring/X: green G means `gps_valid=true` in that
sender's latest successfully saved record; red G means no GPS fix.
G retains the last reported fix state while the ring/X indicates
whether the sender is still transmitting (30-second timeout).
