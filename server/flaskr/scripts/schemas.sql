DROP DATABASE IF EXISTS portfolio_db;
CREATE DATABASE portfolio_db;

USE portfolio_db;

CREATE TABLE `stocks` (
  `stock_id` int NOT NULL AUTO_INCREMENT,
  `ticker` varchar(10) UNIQUE NOT NULL,
  `company_name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`stock_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `holdings` (
  `holding_id` int NOT NULL AUTO_INCREMENT,
  `stock_id` int NOT NULL,
  `shares` decimal(15,4) NOT NULL,
  `cost_basis` decimal(15,2) NOT NULL,
  `purchase_date` date NOT NULL,
  PRIMARY KEY (`holding_id`),
  FOREIGN KEY (`stock_id`) REFERENCES `stocks`(`stock_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
