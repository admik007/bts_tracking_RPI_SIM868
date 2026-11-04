import os
import json
import hashlib
import math
import re
import mysql.connector
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "gps/+/location")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASS = os.environ["MYSQL_PASS"]
MYSQL_DB = os.environ["MYSQL_DB"]

# =========================
# MYSQL
# =========================

db = mysql.connector.connect(
    host=MYSQL_HOST,
    database=MYSQL_DB,
    user=MYSQL_USER,
    password=MYSQL_PASS
)

cursor = db.cursor()

# =========================
# HELPERS
# =========================

def safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def safe_bool(value, default=True):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in (
            "1",
            "true",
            "yes",
            "on"
        )

    return default


# =========================
# BTS AUTO-REGISTRATION
# =========================

def register_new_bts(data, device_id, gps_time, gps_valid, lat, lon, alt,
                     mcc, mnc, cellid, lac, bsic):
    """Register only NEW GSM cells; leave existing surveyed BTS untouched.

    GPS coordinates are a place of reception, never a proven tower location.
    Invalid network identity is ignored. A BTS insert failure must not discard
    an otherwise valid GPS measurement; the caller surrounds it with a savepoint.
    """
    mcc = mcc.strip()
    mnc = mnc.strip()
    if (not re.fullmatch(r"[0-9]{3}", mcc)
            or not re.fullmatch(r"[0-9]{2,3}", mnc)
            or not 0 < cellid <= 9223372036854775807):
        return "skipped"

    valid_position = (
        gps_valid == 1
        and -90 <= lat <= 90 and -180 <= lon <= 180
        and (lat != 0 or lon != 0)
    )
    location_type = "observation" if valid_position else "unknown"
    position_lat = str(lat) if valid_position else ""
    position_lon = str(lon) if valid_position else ""
    position_alt = str(alt) if valid_position else ""

    # GPS measurement time (UTC) is preferred over receipt time for historical
    # replays. DATETIME columns are UTC by convention for this application.
    canonical_time = canonical_utc_time(gps_time)
    observed_at = (
        datetime.fromisoformat(canonical_time).replace(tzinfo=None)
        if canonical_time else datetime.now(timezone.utc).replace(tzinfo=None)
    )
    original_time = gps_time if isinstance(gps_time, str) else ""

    cursor.execute(
        """
        INSERT INTO bts_tracking (
            lat, lon, alt, time, device,
            mcc, mnc, bsic, cellid, lac, address,
            location_type, technology, first_seen, last_seen,
            observations, source
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, 'GSM', %s, %s,
            1, 'gps_tracker'
        )
        ON DUPLICATE KEY UPDATE id = id
        """,
        (
            position_lat, position_lon, position_alt, original_time[:26],
            device_id, mcc, mnc, str(bsic), cellid, str(lac),
            "no info", location_type, observed_at, observed_at
        )
    )
    if cursor.rowcount == 1:
        print("BTS NEW: {}/{}/{} ({})".format(
            mcc, mnc, cellid, location_type
        ))
        return "new"
    return "existing"


# =========================
# MYSQL INSERT
# =========================

def normalize_gps_time(value):
    if not value:
        return None

    try:
        # -------------------------
        # BATCH / OLD PENDING FORMAT
        # 2026-08-08T131928.000Z
        # -------------------------
        if "T" in value:
            date_part, time_part = value.split("T", 1)
            time_part = time_part.rstrip("Z")

            if len(time_part) >= 10 and ":" not in time_part:
                time_part = (
                    time_part[0:2] + ":" +
                    time_part[2:4] + ":" +
                    time_part[4:]
                )

            value = date_part + "T" + time_part + "Z"

        return value

    except Exception as e:
        print("GPS time conversion error:", e)
        return value


# Identity of a GPS measurement must not include server receive time or SQL id.
# Both "2026-08-18T085858.000Z" and "2026-08-18 08:58:58.000"
# normalize to one UTC timestamp. Unexpected/missing timestamps are NOT deduped.
def canonical_utc_time(value):
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    compact = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})(\.\d+)?Z?",
        raw
    )
    if compact:
        raw = "{}T{}:{}:{}{}Z".format(
            compact.group(1), compact.group(2), compact.group(3),
            compact.group(4), compact.group(5) or ""
        )
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except ValueError:
        return None


def measurement_key(device_id, gps_time, values):
    utc_time = canonical_utc_time(gps_time)
    if utc_time is None:
        return None
    # All payload-derived columns, excluding id and server receive timestamp.
    # Do not collapse differing GPS/GSM diagnostics into a single record.
    stable_fields = (
        values[0:6] + values[7:9] +
        values[15:]
    )
    payload = json.dumps(
        [device_id, utc_time, stable_fields],
        separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def insert_record(data, device_id):

    # -------------------------
    # GPS DATA
    # -------------------------

    lat = safe_float(data.get("lat"))
    lon = safe_float(data.get("lon"))
    alt = safe_float(data.get("alt"))
    spd = safe_float(data.get("spd"))
    sat = safe_int(data.get("sat"))
    direction = safe_float(data.get("dir"))

    # -------------------------
    # NETWORK DATA
    # -------------------------

    csq = safe_int(data.get("csq"))
    creg = safe_int(data.get("creg"))
    cgatt = safe_int(data.get("cgatt"))

    mcc = str(data.get("mcc", "") or "")
    mnc = str(data.get("mnc", "") or "")

    bsic = safe_int(data.get("bsic"))
    cellid = safe_int(data.get("cellid"))
    lac = safe_int(data.get("lac"))

    # Old firmware/pending records do not contain gps_valid.
    # Those records were created only from valid GPS fixes.
    gps_valid = 1 if safe_bool(
        data.get("gps_valid"),
        True
    ) else 0

    # -------------------------
    # LEGACY FIELDS
    # -------------------------

    provider = 0
    loadrpi = 0
    cputemp = data.get("cputemp", "")

    # GPS TIME - UTC
    gps_time = normalize_gps_time(
        data.get("time", "")
    )

    # -------------------------
    # SERVER TIME
    # -------------------------

    now = datetime.now()

    # -------------------------
    # MYSQL
    # -------------------------

    sql = """
    INSERT INTO gps_tracking
    (
        lat,
        lon,
        alt,
        acc,
        spd,
        sat,
        time,
        bat,
        ip,
        year,
        month,
        day,
        hour,
        minute,
        second,
        device,
        provider,
        direction,
        devicerpi,
        temprpi,
        loadrpi,
        gps_valid,
        creg,
        cgatt,
        csq,
        mcc,
        mnc,
        bsic,
        cellid,
        lac
    )
    VALUES
    (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s
    )
    """

    values = (
        lat,
        lon,
        alt,
        0,
        spd,
        sat,
        gps_time,
        100.0,
        "",
        now.year,
        now.strftime("%m"),
        now.strftime("%d"),
        now.strftime("%H"),
        now.strftime("%M"),
        now.strftime("%S"),
        "",
        provider,
        direction,
        device_id,
        cputemp,
        loadrpi,
        gps_valid,
        creg,
        cgatt,
        csq,
        mcc,
        mnc,
        bsic,
        cellid,
        lac
    )

    key = measurement_key(device_id, gps_time, values)
    if key is not None:
        try:
            cursor.execute(
                "INSERT INTO gps_received_keys (point_key) VALUES (%s)",
                (key,)
            )
        except mysql.connector.IntegrityError as e:
            if e.errno == 1062:  # duplicate key, already stored
                return False
            raise
    else:
        print("WARNING: invalid GPS time; key not registered:", repr(gps_time))

    # The registry insert and GPS INSERT are in the SAME transaction:
    # any rollback removes both, so a failed GPS insert cannot reserve a key.
    cursor.execute(sql, values)

    # BTS registration is best-effort. Its own savepoint ensures that a missing
    # table, privilege error or unexpected BTS value never rolls back GPS data.
    cursor.execute("SAVEPOINT bts_registration")
    try:
        register_new_bts(
            data, device_id, gps_time, gps_valid, lat, lon, alt,
            mcc, mnc, cellid, lac, bsic
        )
    except mysql.connector.Error as e:
        cursor.execute("ROLLBACK TO SAVEPOINT bts_registration")
        print("BTS REGISTER ERROR (GPS preserved):", e)
    except Exception as e:
        cursor.execute("ROLLBACK TO SAVEPOINT bts_registration")
        print("BTS REGISTER ERROR (GPS preserved):", e)
    finally:
        cursor.execute("RELEASE SAVEPOINT bts_registration")
    return True


# =========================
# MQTT
# =========================

def on_connect(client, userdata, flags, rc):

    print("MQTT connected:", rc)

    client.subscribe(MQTT_TOPIC)

    print("Subscribed:", MQTT_TOPIC)


def on_message(client, userdata, msg):
    print()
    print("MQTT:", msg.topic)

    try:
        data = json.loads(msg.payload.decode("utf-8"))
        parts = msg.topic.split("/")
        if len(parts) != 3 or parts[0] != "gps" or parts[2] != "location":
            raise ValueError("Unexpected MQTT topic: " + msg.topic)
        device_id = parts[1]
        if not device_id or len(device_id) > 16:
            raise ValueError("Invalid device ID in topic")

        records = data["points"] if "points" in data else [data]
        if not isinstance(records, list):
            raise ValueError("MQTT 'points' must be a list")

        # One transaction per MQTT message. Each individual record gets a
        # SAVEPOINT so a malformed record cannot poison the rest of a batch.
        db.ping(reconnect=True, attempts=3, delay=2)
        inserted = 0
        duplicates = 0
        errors = 0
        for record in records:
            cursor.execute("SAVEPOINT gps_record")
            try:
                if not isinstance(record, dict):
                    raise ValueError("GPS record must be a JSON object")
                stored = insert_record(record, device_id)
                if stored:
                    inserted += 1
                else:
                    duplicates += 1
                cursor.execute("RELEASE SAVEPOINT gps_record")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT gps_record")
                cursor.execute("RELEASE SAVEPOINT gps_record")
                errors += 1
                print("GPS RECORD ERROR:", e)
        db.commit()
        print("MYSQL: stored={}, duplicate={}, errors={}, received={}".format(
            inserted, duplicates, errors, len(records)
        ))
        if errors:
            print("WARNING: failed records were NOT stored; investigate MQTT log")
    except Exception as e:
        db.rollback()
        print("MQTT ERROR:", e)


# =========================
# START
# =========================

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

print("Connecting MQTT...")

client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60
)

client.loop_forever()
