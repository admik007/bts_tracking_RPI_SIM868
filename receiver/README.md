# BTS Tracking – central AP receiver

This directory belongs to **admik007/bts_tracking_RPI_SIM868** (not the retired `bts_tracking` repository).

## Boot and OTA

The existing `firmware/main.py` is reused **unchanged**:

1. It waits 15 seconds for Thonny and attempts to connect to the infrastructure Wi-Fi from `config_wifi.py`.
2. If Wi-Fi connects, it checks `http://HOST/firmware/<DEVICE_ID>/manifest.json` and installs the verified OTA files.
3. If Wi-Fi is unavailable, it skips OTA.
4. In both cases, `main.py` imports the local `app.py` and runs `app.run()`.
5. `receiver/app.py` disconnects STA, activates the `BTS-TRACKING` AP at `192.168.4.1`, and listens on TCP port 5000.

**Note:** This means the AP appears only *after* the bootloader's 15-second Thonny delay and bounded Wi-Fi connection attempts.

## Pico files

Copy these **existing** files from `firmware/` to the receiver Pico:

- `main.py`
- `config.py` (created from `config.py.example`)
- `config_wifi.py` (created from `config_wifi.py.example`)

Copy `receiver/app.py` as `app.py` on the Pico. The SIM868 driver is not needed on the receiver.

`config_wifi.py` must contain the infrastructure Wi-Fi credentials and `HOST` pointing to your Apache firmware host. Keep actual credentials outside Git.

## Receive protocol – first stage

Sender connects to `192.168.4.1:5000` and sends one UTF-8 JSON object per line (newline required). Example:

```text
{"device":"e661385283997828","mcc":"231","mnc":"02","lac":12345,"cellid":67890,"technology":"GSM"}\n
```

The receiver prints `BTS_JSON:{...}` on USB serial and answers `OK\n`. Invalid records return `ERR json\n`. Currently records are **not saved**; a response confirms parsing/printing only, **not durable storage**. SD persistence, LCD and buttons will be implemented in subsequent stages. Sender-side TCP transport has not yet been added.

## Server-side OTA publishing

From the Git checkout:

```bash
git pull
bash scripts/deploy-receiver.sh <RECEIVER_DEVICE_ID>
```

Default target is:

```text
/opt/bts_tracking_RPI_SIM868/firmware/<RECEIVER_DEVICE_ID>/
    app.py
    manifest.json
```

Override the root with `OTA_ROOT=/another/path` if required. Apache must serve the files under `/firmware/<DEVICE_ID>/`.

The deploy script generates SHA-256 and a content-derived version, compatible with the existing `main.py`. `main.py`, `config.py`, and `config_wifi.py` are never pushed by OTA.
