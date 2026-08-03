DROP DATABASE IF EXISTS portfolio_db;
CREATE DATABASE portfolio_db;

USE portfolio_db;

CREATE TABLE `accounts` (
  `id` int AUTO_INCREMENT,
  `balance` decimal(15,2) NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `transactions` (
  `tr_id` int AUTO_INCREMENT,
  `ticker` varchar(10) NOT NULL,
  `amount` decimal(15,4) NOT NULL,
  `cost_basis` decimal(15,2) NOT NULL,
  `transaction_date` datetime NOT NULL,
  PRIMARY KEY (`tr_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `cash_transactions` (
  `id` int AUTO_INCREMENT,
  `amount` decimal(15,2) NOT NULL,
  `transaction_date` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

INSERT INTO `accounts` (`balance`) VALUES (30000.00);
