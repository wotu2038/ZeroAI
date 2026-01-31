-- ============================================================
-- MySQL 数据库初始化脚本
-- ============================================================
-- 
-- 【重要说明】
-- 此脚本由 docker-compose 在 MySQL 容器首次启动时自动执行。
-- 数据库名和用户名通过 docker-compose.backend.yml 的环境变量配置：
--   - MYSQL_DATABASE: 数据库名（从 .env 读取）
--   - MYSQL_USER: 数据库用户（从 .env 读取）
-- 
-- 实际数据库已由 docker-compose 的 MYSQL_DATABASE 环境变量自动创建，
-- 此脚本仅作为备用/参考。
-- 
-- 表结构由 SQLAlchemy 在应用启动时自动创建，无需手动干预。
-- ============================================================

-- 设置字符集（对后续创建的表生效）
SET NAMES utf8mb4;
SET CHARACTER_SET_CLIENT = utf8mb4;
SET CHARACTER_SET_RESULTS = utf8mb4;
SET COLLATION_CONNECTION = utf8mb4_unicode_ci;

