/*
QTPy: Algorithmic Trading Library
https://github.com/ranaroussi/qtpylib
Copyright (c) Ran Aroussi

Licensed under the GNU Lesser General Public License, v3.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.gnu.org/licenses/lgpl-3.0.en.html

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

SET foreign_key_checks = 0;

CREATE TABLE IF NOT EXISTS `_version_` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `version` varchar(8) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;


CREATE TABLE IF NOT EXISTS `symbols` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `symbol` varchar(24) DEFAULT NULL,
  `symbol_group` varchar(18) DEFAULT NULL,
  `asset_class` varchar(3) DEFAULT NULL,
  `expiry` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `symbol` (`symbol`),
  KEY `symbol_group` (`symbol_group`),
  KEY `asset_class` (`asset_class`),
  KEY `expiry` (`expiry`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

ALTER TABLE `symbols`
  MODIFY `symbol` varchar(24),
  MODIFY `symbol_group` varchar(18);


CREATE TABLE IF NOT EXISTS `bars` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `datetime` datetime NOT NULL,
  `symbol_id` int(11) unsigned NOT NULL,
  `open` double unsigned DEFAULT NULL,
  `high` double unsigned DEFAULT NULL,
  `low` double unsigned DEFAULT NULL,
  `close` double unsigned DEFAULT NULL,
  `volume` int(11) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`datetime`,`symbol_id`),
  KEY `datetime` (`datetime`),
  KEY `symbol_id` (`symbol_id`),
  CONSTRAINT `bar_symbol` FOREIGN KEY (`symbol_id`) REFERENCES `symbols` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;


CREATE TABLE IF NOT EXISTS `ticks` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `datetime` datetime(3) NOT NULL,
  `symbol_id` int(11) unsigned NOT NULL,
  `bid` double unsigned DEFAULT NULL,
  `bidsize` int(11) unsigned DEFAULT NULL,
  `ask` double unsigned DEFAULT NULL,
  `asksize` int(11) unsigned DEFAULT NULL,
  `last` double unsigned DEFAULT NULL,
  `lastsize` int(11) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`datetime`,`symbol_id`),
  KEY `datetime` (`datetime`),
  KEY `symbol_id` (`symbol_id`),
  CONSTRAINT `tick_symbol` FOREIGN KEY (`symbol_id`) REFERENCES `symbols` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `greeks` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `tick_id` int(11) unsigned DEFAULT NULL,
  `bar_id` int(11) unsigned DEFAULT NULL,
  `price` double unsigned DEFAULT NULL,
  `underlying` double unsigned DEFAULT NULL,
  `dividend` double unsigned DEFAULT NULL,
  `volume` int(11) unsigned DEFAULT NULL,
  `iv` double unsigned DEFAULT NULL,
  `oi` double unsigned DEFAULT NULL,
  `delta` decimal(3,2) DEFAULT NULL,
  `gamma` decimal(3,2) DEFAULT NULL,
  `theta` decimal(3,2) DEFAULT NULL,
  `vega` decimal(3,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `tick_id` (`tick_id`),
  KEY `bar_id` (`bar_id`),
  CONSTRAINT `bar_data` FOREIGN KEY (`bar_id`) REFERENCES `bars` (`id`),
  CONSTRAINT `tick_data` FOREIGN KEY (`tick_id`) REFERENCES `ticks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `trades` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `algo` varchar(32) DEFAULT NULL,
  `symbol` varchar(12) DEFAULT NULL,
  `direction` varchar(5) DEFAULT NULL,
  `quantity` int(11) unsigned DEFAULT NULL,
  `entry_time` datetime(6) DEFAULT NULL,
  `exit_time` datetime(6) DEFAULT NULL,
  `exit_reason` varchar(8) DEFAULT NULL,
  `order_type` varchar(6) DEFAULT NULL,
  `market_price` double unsigned DEFAULT NULL,
  `target` double unsigned DEFAULT NULL,
  `stop` double unsigned DEFAULT NULL,
  `entry_price` double unsigned DEFAULT NULL,
  `exit_price` double unsigned DEFAULT NULL,
  `realized_pnl` double DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`algo`,`symbol`,`entry_time`),
  KEY `algo` (`algo`),
  KEY `symbol` (`symbol`),
  KEY `entry_time` (`entry_time`),
  KEY `exit_time` (`exit_time`),
  KEY `exit_reason` (`exit_reason`),
  KEY `order_type` (`order_type`),
  KEY `market_price` (`market_price`),
  KEY `exit_price` (`exit_price`),
  KEY `entry_price` (`entry_price`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

SET foreign_key_checks = 1;