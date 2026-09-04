-- 已初始化环境升级：增加 JWT 统一失效版本号。
-- 本迁移只执行一次；全新环境直接执行 init_mysql.sql 即可。

USE `AI-learn`;

ALTER TABLE `users`
  ADD COLUMN `token_version` INT UNSIGNED NOT NULL DEFAULT 0
  COMMENT '统一撤销旧令牌的版本号'
  AFTER `total_xp`;
