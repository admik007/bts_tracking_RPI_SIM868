-- Run once in the existing MariaDB database used by GPS Tracking.
-- Existing bts_tracking (UNIQUE technology,mcc,mnc,cellid) remains unchanged.
-- Raw reception measurements are stored here, independently of BTS identity.
CREATE TABLE IF NOT EXISTS bts_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    point_key BINARY(32) NULL,
    device VARCHAR(32) NOT NULL,
    observed_at DATETIME(6) NULL,
    received_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    lat DOUBLE NULL,
    lon DOUBLE NULL,
    alt DOUBLE NULL,
    sat TINYINT UNSIGNED NULL,
    speed_kmh DOUBLE NULL,
    course DOUBLE NULL,
    gps_valid TINYINT(1) NOT NULL DEFAULT 0,
    technology VARCHAR(16) NOT NULL,
    mcc VARCHAR(3) NOT NULL,
    mnc VARCHAR(3) NOT NULL,
    cellid BIGINT NOT NULL,
    lac INT NULL,
    bsic INT NULL,
    csq INT NULL,
    creg INT NULL,
    cgreg INT NULL,
    source VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bts_point (point_key),
    INDEX idx_bts_device_time (device, observed_at),
    INDEX idx_bts_cell_time (technology, mcc, mnc, cellid, observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
