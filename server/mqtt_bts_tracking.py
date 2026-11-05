"""BTS MQTT -> MariaDB observations + non-destructive cell registration.

Based on GPS tracker server/mqtt_gps_tracking.py. Standalone process.
Requires server/schema_bts_observations.sql to be applied first.
"""
import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime, timezone

import mysql.connector
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("bts_mqtt")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "bts/+/location")
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASS = os.environ["MYSQL_PASS"]
MYSQL_DB = os.environ["MYSQL_DB"]

DB = mysql.connector.connect(
    host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASS, database=MYSQL_DB,
    autocommit=False,
)
CURSOR = DB.cursor()


def number(value, typ, default=None):
    if value is None or value == "":
        return default
    try:
        parsed = typ(value)
        if isinstance(parsed, float) and not math.isfinite(parsed):
            return default
        return parsed
    except (ValueError, TypeError, OverflowError):
        return default


def utc_time(value):
    if not isinstance(value, str) or not value.strip():
        return None, None
    raw = value.strip()
    # Support both normal and historical compact timestamps.
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})(\.\d+)?Z?", raw)
    if m:
        raw = "{}T{}:{}:{}{}Z".format(*[m.group(i) or "" for i in range(1, 6)])
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=None), dt.isoformat(timespec="microseconds")
    except ValueError:
        return None, None


def require_string(v, label, max_length):
    if not isinstance(v, str) or not v or len(v) > max_length:
        raise ValueError("Invalid {}".format(label))
    return v


def normalize(data, topic):
    if not isinstance(data, dict):
        raise ValueError("MQTT payload must be one JSON object")
    match = re.fullmatch(r"bts/([0-9a-fA-F]{16})/location", topic)
    if not match:
        raise ValueError("Invalid BTS MQTT topic: {}".format(topic))
    device = match.group(1).lower()
    if require_string(data.get("device"), "device", 16).lower() != device:
        raise ValueError("Device ID differs from MQTT topic")

    mcc = str(data.get("mcc") or "").strip()
    mnc = str(data.get("mnc") or "").strip()
    technology = str(data.get("technology") or "GSM").upper()
    cellid = number(data.get("cellid"), int)
    lac = number(data.get("lac"), int)
    bsic = number(data.get("bsic"), int)
    if (not re.fullmatch(r"\d{3}", mcc)
            or not re.fullmatch(r"\d{2,3}", mnc)
            or technology != "GSM"
            or cellid is None or not 0 < cellid <= 9223372036854775807):
        raise ValueError("Invalid GSM cell identity")

    dt, canonical = utc_time(data.get("time"))
    valid = data.get("gps_valid") is True or data.get("gps_valid") == 1
    lat, lon = number(data.get("lat"), float), number(data.get("lon"), float)
    if not (valid and lat is not None and lon is not None
            and -90 <= lat <= 90 and -180 <= lon <= 180
            and (lat != 0 or lon != 0)):
        lat, lon, valid = None, None, False
    alt = number(data.get("alt"), float) if valid else None
    sat = number(data.get("sat"), int)
    if sat is not None and not 0 <= sat <= 255:
        sat = None

    values = {
        "device": device, "observed_at": dt,
        "lat": lat, "lon": lon, "alt": alt,
        "sat": sat,
        "speed_kmh": number(data.get("speed_kmh"), float),
        "course": number(data.get("course"), float),
        "gps_valid": int(valid),
        "technology": technology, "mcc": mcc, "mnc": mnc,
        "cellid": cellid, "lac": lac, "bsic": bsic,
        "csq": number(data.get("csq"), int),
        "creg": number(data.get("creg"), int),
        "cgreg": number(data.get("cgreg"), int),
        "source": str(data.get("source") or "bts_pico_sim868")[:64],
        "original_time": str(data.get("time") or "")[:26],
    }
    # For valid timestamps use original observation data; no server-receipt
    # fields, IDs or MQTT metadata. Retried QoS1 messages get same key.
    # No timestamp => NULL key, so distinct untimed samples aren't collapsed.
    if canonical:
        identity = {k: values[k] for k in values if k not in ("original_time", "observed_at")}
        identity["utc_time"] = canonical
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
        values["point_key"] = hashlib.sha256(payload.encode("utf-8")).digest()
    else:
        values["point_key"] = None
    return values


INSERT_OBSERVATION = """
INSERT INTO bts_observations (
  point_key, device, observed_at, lat, lon, alt, sat, speed_kmh, course,
  gps_valid, technology, mcc, mnc, cellid, lac, bsic, csq, creg, cgreg, source
) VALUES (
  %(point_key)s, %(device)s, %(observed_at)s, %(lat)s, %(lon)s, %(alt)s,
  %(sat)s, %(speed_kmh)s, %(course)s, %(gps_valid)s, %(technology)s,
  %(mcc)s, %(mnc)s, %(cellid)s, %(lac)s, %(bsic)s, %(csq)s,
  %(creg)s, %(cgreg)s, %(source)s
)
"""

REGISTER_CELL = """
INSERT INTO bts_tracking (
  lat, lon, alt, time, device, mcc, mnc, bsic, cellid, lac, address,
  location_type, technology, first_seen, last_seen, observations, source
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
  %s, %s, %s, %s, 1, %s
)
ON DUPLICATE KEY UPDATE id = id
"""


def store(values):
    try:
        CURSOR.execute(INSERT_OBSERVATION, values)
    except mysql.connector.IntegrityError as exc:
        if exc.errno == 1062 and values["point_key"] is not None:
            DB.rollback()
            return "duplicate"
        raise
    observed = values["observed_at"] or datetime.now(timezone.utc).replace(tzinfo=None)
    has_location = values["gps_valid"] == 1
    params = (
        str(values["lat"]) if has_location else "",
        str(values["lon"]) if has_location else "",
        str(values["alt"]) if has_location and values["alt"] is not None else "",
        values["original_time"], values["device"], values["mcc"], values["mnc"],
        str(values["bsic"] if values["bsic"] is not None else ""),
        values["cellid"], str(values["lac"] if values["lac"] is not None else ""),
        "no info", "observation" if has_location else "unknown",
        values["technology"], observed, observed, "bts_receiver",
    )
    # GPS subscriber performs same non-destructive registration, so existing
    # manually surveyed BTS addresses/coordinates are never overwritten.
    CURSOR.execute(REGISTER_CELL, params)
    DB.commit()
    return "stored"


def on_connect(client, userdata, flags, rc, properties=None):
    code = int(rc)
    if code == 0:
        client.subscribe(MQTT_TOPIC, qos=1)
        LOG.info("Subscribed to %s", MQTT_TOPIC)
    else:
        LOG.error("MQTT connection rejected: %s", rc)


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
        values = normalize(data, message.topic)
        DB.ping(reconnect=True, attempts=3, delay=2)
        status = store(values)
        LOG.info("%s device=%s MCCMNC=%s%s CellID=%s UTC=%s",
                 status, values["device"], values["mcc"], values["mnc"],
                 values["cellid"], values["observed_at"])
    except Exception:
        DB.rollback()
        LOG.exception("BTS ingest failed topic=%s (not stored)", message.topic)


def main():
    # paho-mqtt 1.x and 2.x callback API compatibility.
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()
    if MQTT_USER is not None:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    LOG.info("Connecting to MQTT %s:%s", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
