SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `bts_tracking` (
  `id` int(11) NOT NULL,
  `lat` varchar(14) NOT NULL DEFAULT '',
  `lon` varchar(14) NOT NULL DEFAULT '',
  `alt` varchar(10) NOT NULL DEFAULT '',
  `time` varchar(26) NOT NULL DEFAULT '',
  `device` varchar(255) NOT NULL DEFAULT '',
  `mcc` varchar(3) NOT NULL,
  `mnc` varchar(3) NOT NULL,
  `bsic` varchar(8) NOT NULL DEFAULT '',
  `cellid` bigint(20) NOT NULL,
  `lac` varchar(8) NOT NULL DEFAULT '',
  `address` varchar(255) NOT NULL DEFAULT 'no info',
  `location_type` enum('tower','observation','unknown') NOT NULL DEFAULT 'unknown',
  `technology` varchar(12) NOT NULL DEFAULT 'GSM',
  `first_seen` datetime DEFAULT NULL,
  `last_seen` datetime DEFAULT NULL,
  `observations` bigint(20) UNSIGNED NOT NULL DEFAULT 0,
  `source` varchar(32) NOT NULL DEFAULT 'legacy'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `bts_tracking`
--
ALTER TABLE `bts_tracking`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_bts_identity` (`technology`,`mcc`,`mnc`,`cellid`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `bts_tracking`
--
ALTER TABLE `bts_tracking`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
COMMIT;
