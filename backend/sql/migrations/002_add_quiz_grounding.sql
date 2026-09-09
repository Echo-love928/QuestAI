-- 已初始化环境升级：保存题库生成依据和来源快照。
-- 适用版本：MySQL 8.0+；可重复执行，不保存抓取的网页正文。

USE `AI-learn`;

DROP PROCEDURE IF EXISTS `add_quiz_grounding_columns`;

DELIMITER //
CREATE PROCEDURE `add_quiz_grounding_columns`()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'AI-learn'
      AND TABLE_NAME = 'quiz_sessions'
      AND COLUMN_NAME = 'grounding_mode'
  ) THEN
    ALTER TABLE `quiz_sessions`
      ADD COLUMN `grounding_mode` VARCHAR(32) NULL
      COMMENT 'user_content、web_search、url_extract 或 mixed'
      AFTER `source_type`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'AI-learn'
      AND TABLE_NAME = 'quiz_sessions'
      AND COLUMN_NAME = 'sources_json'
  ) THEN
    ALTER TABLE `quiz_sessions`
      ADD COLUMN `sources_json` JSON NULL
      COMMENT '生成时的公开来源快照，不含网页正文'
      AFTER `questions_json`;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'AI-learn'
      AND TABLE_NAME = 'quiz_sessions'
      AND COLUMN_NAME = 'researched_at'
  ) THEN
    ALTER TABLE `quiz_sessions`
      ADD COLUMN `researched_at` DATETIME(3) NULL
      COMMENT '网络资料获取时间'
      AFTER `sources_json`;
  END IF;
END//
DELIMITER ;

CALL `add_quiz_grounding_columns`();
DROP PROCEDURE IF EXISTS `add_quiz_grounding_columns`;
