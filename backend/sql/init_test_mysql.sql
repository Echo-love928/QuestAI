-- AI闯关学习：隔离的后端 TDD 测试数据库。
-- 先执行 init_mysql.sql 和所有生产迁移，再执行本文件。

CREATE DATABASE IF NOT EXISTS `AI-learn-test`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `AI-learn-test`.`users`
  LIKE `AI-learn`.`users`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`quiz_sessions`
  LIKE `AI-learn`.`quiz_sessions`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`answer_records`
  LIKE `AI-learn`.`answer_records`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`reports`
  LIKE `AI-learn`.`reports`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`quiz_generation_tasks`
  LIKE `AI-learn`.`quiz_generation_tasks`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`knowledge_bases`
  LIKE `AI-learn`.`knowledge_bases`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`knowledge_documents`
  LIKE `AI-learn`.`knowledge_documents`;
CREATE TABLE IF NOT EXISTS `AI-learn-test`.`document_ingestion_tasks`
  LIKE `AI-learn`.`document_ingestion_tasks`;
