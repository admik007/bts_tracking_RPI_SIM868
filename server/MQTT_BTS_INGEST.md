# MQTT BTS subscriber on Debian / MariaDB

Standalone server receiver inspired by
[`mqtt_gps_tracking.py`](https://github.com/admik007/gps_tracking_RPI_SIM868/blob/main/server/mqtt_gps_tracking.py).
The existing GPS subscriber/service is **not modified**.

## Storage semantics

- Listen to `bts/+/location`, as sent by the BTS receiver over MQTT TCP 1883.
- Store **each unique timestamped measurement** in new
  `bts_observations`. Deduplication SHA-256 includes sender, normalized
  UTC timestamp and all relevant measured fields, excluding server receipt
  time. This preserves successive five-second observations even when
  BTS CellID does not change.
- For a record without a valid timestamp, `point_key` is NULL: record
  is stored, but automatic deduplication is not possible.
- Register only **new GSM identities** in existing `bts_tracking`
  using the preexisting unique key
  `(technology,mcc,mnc,cellid)`. Existing cells, known addresses and
  manually surveyed coordinates are never overwritten.
- A valid GPS coordinate is an **observation location**, not a verified
  tower location.
- Insert into both tables in one MariaDB transaction. All BTS measurements
  (including `gps_valid=false`) are eligible for raw observation storage.

## Installation

Use the same MariaDB database where GPS Tracking maintains `bts_tracking`.
Verify the current `bts_tracking` schema contains the normalized
`UNIQUE KEY idx_bts_identity (technology,mcc,mnc,cellid)`.

```bash
cd /opt/bts_tracking_RPI_SIM868
git pull
python3 -m py_compile server/mqtt_bts_tracking.py
# Run the SQL schema once with an authorized MariaDB account:
mysql -u YOUR_SQL_USER -p YOUR_EXISTING_DATABASE < server/schema_bts_observations.sql

# Use the same DB user/DB name as the existing GPS MQTT subscriber if desired.
cp server/mqtt_bts_connect.conf.example server/mqtt_bts_connect.conf
chmod 600 server/mqtt_bts_connect.conf
# Edit MYSQL_USER, MYSQL_PASS, MYSQL_DB, broker parameters in the local file.
# Do NOT commit that file.
```

For Debian system Python, install
`python3-mysql.connector` / `python3-paho-mqtt` if available on your
Debian release, or use the Python environment already configured for
the existing GPS subscriber. Adjust `ExecStart` if it runs in a virtualenv.

```bash
cp server/mqtt_bts_mysql.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mqtt_bts_mysql.service
journalctl -u mqtt_bts_mysql.service -f
```

If using an existing Python venv, replace `/usr/bin/python3` in
`ExecStart` with that interpreter's absolute path.

**Important:** the MQTT/MySQL account must have INSERT on
`bts_observations` and INSERT/UPDATE on `bts_tracking`. The latter
is needed by the non-destructive `ON DUPLICATE KEY UPDATE id=id`
even though no existing BTS location is changed.

The reader uses QoS 1, but the MQTT broker may acknowledge reception to
the Pico before the MariaDB insert finishes. The Pico-side saved cursor
does **not** imply successful database insertion. Invalid records/errors
are logged by this subscriber and need investigation/replay. A later
application-level acknowledgment can improve end-to-end guarantees.

## Checks

Monitor new messages from the Pico (start before pressing KEY0):

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'bts/+/location' -v
```

Watch insert activity:

```bash
journalctl -u mqtt_bts_mysql.service -f
```

Inspect latest samples:

```sql
SELECT id,device,observed_at,mcc,mnc,cellid,lac,bsic,lat,lon
FROM bts_observations ORDER BY id DESC LIMIT 10;

SELECT technology,mcc,mnc,cellid,source,location_type
FROM bts_tracking
WHERE technology='GSM' AND mcc='231' AND mnc='01' AND cellid=59812;
```

**Already-uploaded MQTT QoS 1 messages are not retained** for this
new subscriber. To replay them after installing subscriber, the
receiver's SD source JSONL data still exist, but resetting its saved
cursor needs a deliberate backup and replay procedure. Do not remove
cursor files while the receiver is operating.

The service uses a local credentials file and does not touch the
existing `mqtt_gps_mysql.service`.
