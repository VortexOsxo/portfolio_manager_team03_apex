DROP DATABASE IF EXISTS portfolio_db;
CREATE DATABASE portfolio_db;

USE portfolio_db;

CREATE TABLE `accounts` (
  `id` int AUTO_INCREMENT,
  `balance` decimal(15,2) NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `transactions` (
  `tr_id`            int          AUTO_INCREMENT,
  `type`             ENUM('buy','sell','deposit','withdrawal') NOT NULL DEFAULT 'buy',
  `ticker`           varchar(10)  NULL,
  `amount`           decimal(15,4) NOT NULL,
  `cost_basis`       decimal(15,2) NULL,
  `transaction_date` datetime     NOT NULL,
  PRIMARY KEY (`tr_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

INSERT INTO `accounts` (`balance`) VALUES (30000.00);

INSERT INTO `transactions` (`type`, `ticker`, `amount`, `cost_basis`, `transaction_date`)
VALUES ('deposit', NULL, 30000.00, NULL, '2024-01-01 00:00:00');
