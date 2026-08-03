DROP DATABASE IF EXISTS portfolio_db;
CREATE DATABASE portfolio_db;

USE portfolio_db;

CREATE TABLE `accounts` (
  `id` int AUTO_INCREMENT,
  `username` varchar(50) UNIQUE NOT NULL,
  `password` varchar(255) NOT NULL,
  `balance` decimal(15,2) NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `transactions` (
  `tr_id`            int          AUTO_INCREMENT,
  `account_id`       int          NOT NULL,
  `type`             ENUM('buy','sell','deposit','withdrawal') NOT NULL DEFAULT 'buy',
  `ticker`           varchar(10)  NULL,
  `amount`           decimal(15,4) NOT NULL,
  `cost_basis`       decimal(15,2) NULL,
  `transaction_date` datetime     NOT NULL,
  PRIMARY KEY (`tr_id`),
  FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

