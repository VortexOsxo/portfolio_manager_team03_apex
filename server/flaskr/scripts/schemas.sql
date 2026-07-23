DROP DATABASE IF EXISTS portfolio_db;
CREATE DATABASE portfolio_db;

USE portfolio_db;

CREATE TABLE `holdings` (
  `holding_id` int AUTO_INCREMENT,
  `ticker` varchar(10) UNIQUE NOT NULL,
  `amount` decimal(15,4) NOT NULL,
  `cost_basis` decimal(15,2) NOT NULL,
  `purchase_date` date NOT NULL,
  PRIMARY KEY (`holding_id`),
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
