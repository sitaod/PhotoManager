-- We do not actually run this script, it's just for reference.
-- The database and tables are created via SQLAlchemy in init_db.py

-- Create database
CREATE DATABASE photomanager CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE photomanager;

-- User table: stores user account information
CREATE TABLE `user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'User ID',
  `username` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Username',
  `email` VARCHAR(100) NOT NULL UNIQUE COMMENT 'Email address',
  `password_hash` VARCHAR(255) NOT NULL COMMENT 'Password hash',
  `register_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Registration time',
  PRIMARY KEY (`id`),
  INDEX `idx_username` (`username`),
  INDEX `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Image table: stores image metadata
CREATE TABLE `image` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Image ID',
  `user_id` BIGINT UNSIGNED NOT NULL COMMENT 'User ID (foreign key)',
  `image_path` VARCHAR(512) NOT NULL COMMENT 'Original image path',
  `thumbnail_path` VARCHAR(512) NOT NULL COMMENT 'Thumbnail image path',
  `upload_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Upload time',
  `shoot_time` DATETIME DEFAULT NULL COMMENT 'Photo shoot time (from EXIF)',
  `shoot_location` VARCHAR(200) DEFAULT NULL COMMENT 'Photo shoot location (from EXIF GPS)',
  `resolution` VARCHAR(50) DEFAULT NULL COMMENT 'Image resolution (format: WxH)',
  PRIMARY KEY (`id`),
  INDEX `idx_user_id` (`user_id`),
  CONSTRAINT `fk_image_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;