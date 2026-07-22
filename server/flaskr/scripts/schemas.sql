CREATE DATABASE IF NOT EXISTS portfolio_db;
   USE portfolio_db;

CREATE TABLE `holdings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `stock_ticker` varchar(10) NOT NULL,
  `company_name` varchar(100) DEFAULT NULL,
  `shares` decimal(15,4) NOT NULL,
  `cost_basis` decimal(15,2) NOT NULL,
  `current_price` decimal(15,2) DEFAULT NULL,
  `purchase_date` date NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;