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
This change does not initialize or read any buttons. Do not use button
GP17 until its wiring is resolved. LCD display alone uses no SD GPIO.

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
bootstrap `main.py`. This step does not implement keys or MQTT yet.

Sender rows are assigned in order of first successfully stored message during
this boot, and each device's row updates independently. Additional senders are
still logged to SD, but are not shown on this three-row screen. Row numbering
is local to the current boot, not a permanent device assignment.
