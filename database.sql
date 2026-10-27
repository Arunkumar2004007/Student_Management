-- Run with: mysql -u root -p < database.sql
CREATE DATABASE IF NOT EXISTS student_management
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE student_management;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin','teacher') NOT NULL DEFAULT 'teacher',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_no VARCHAR(20) NOT NULL,
  name VARCHAR(100) NOT NULL,
  class_name VARCHAR(10) NOT NULL,
  email VARCHAR(120),
  phone VARCHAR(20),
  guardian VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_roll_class (roll_no, class_name),
  INDEX idx_name (name),
  INDEX idx_class (class_name)
);

-- Use a limited account for the app instead of root:
-- CREATE USER 'sms_app'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON student_management.* TO 'sms_app'@'localhost';

INSERT IGNORE INTO students (roll_no, name, class_name, email, phone, guardian) VALUES
('101','Aarav Sharma','8A','aarav@school.example','9845010001','Meena Sharma'),
('102','Diya Nair','8A','diya@school.example','9845010002','Suresh Nair'),
('103','Kabir Rao','8B','kabir@school.example','9845010003','Latha Rao'),
('104','Meera Iyer','9A','meera@school.example','9845010004','Ramesh Iyer');
