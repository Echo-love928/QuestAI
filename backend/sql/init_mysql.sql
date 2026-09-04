-- AI闯关学习：用户系统 MySQL 初始化脚本
-- 适用版本：MySQL 8.0+
-- 特性：可重复执行；只创建数据库和表，不写入演示数据。

CREATE DATABASE IF NOT EXISTS `AI-learn`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE `AI-learn`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户主键',
  `openid` VARCHAR(64) NOT NULL COMMENT '微信小程序用户唯一标识',
  `nickname` VARCHAR(32) NOT NULL DEFAULT '学习者' COMMENT '用户昵称',
  `avatar_url` VARCHAR(2048) NULL COMMENT '用户头像地址',
  `total_xp` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '累计经验值',
  `token_version` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '统一撤销旧令牌的版本号',
  `last_login_at` DATETIME(3) NULL COMMENT '最近登录时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_openid` (`openid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='微信小程序用户';

CREATE TABLE IF NOT EXISTS `quiz_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '闯关记录主键',
  `quiz_id` VARCHAR(64) NOT NULL COMMENT '对外使用的闯关标识',
  `user_id` BIGINT UNSIGNED NOT NULL COMMENT '所属用户',
  `title` VARCHAR(255) NOT NULL COMMENT '闯关标题',
  `summary` TEXT NULL COMMENT '闯关内容摘要',
  `source_type` VARCHAR(32) NOT NULL DEFAULT 'text' COMMENT '输入来源类型',
  `user_input` LONGTEXT NOT NULL COMMENT '用户原始输入内容',
  `questions_json` JSON NOT NULL COMMENT '生成时的完整题目快照',
  `question_count` SMALLINT UNSIGNED NOT NULL COMMENT '题目数量',
  `correct_count` SMALLINT UNSIGNED NULL COMMENT '答对题目数量',
  `accuracy` DECIMAL(5,2) NULL COMMENT '正确率，范围 0.00-100.00',
  `xp_earned` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本次获得经验值',
  `duration_ms` BIGINT UNSIGNED NULL COMMENT '本次闯关总用时（毫秒）',
  `status` VARCHAR(20) NOT NULL DEFAULT 'generated' COMMENT 'generated 或 completed',
  `completed_at` DATETIME(3) NULL COMMENT '完成时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_quiz_sessions_quiz_id` (`quiz_id`),
  KEY `idx_quiz_sessions_user_created` (`user_id`, `created_at`),
  KEY `idx_quiz_sessions_user_status_completed` (`user_id`, `status`, `completed_at`),
  CONSTRAINT `fk_quiz_sessions_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `chk_quiz_sessions_status`
    CHECK (`status` IN ('generated', 'completed')),
  CONSTRAINT `chk_quiz_sessions_accuracy`
    CHECK (`accuracy` IS NULL OR (`accuracy` >= 0 AND `accuracy` <= 100)),
  CONSTRAINT `chk_quiz_sessions_counts`
    CHECK (`correct_count` IS NULL OR `correct_count` <= `question_count`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='用户闯关会话及题目快照';

CREATE TABLE IF NOT EXISTS `answer_records` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '答题记录主键',
  `quiz_session_id` BIGINT UNSIGNED NOT NULL COMMENT '所属闯关记录',
  `question_id` VARCHAR(64) NOT NULL COMMENT '题目业务标识',
  `question_order` SMALLINT UNSIGNED NOT NULL COMMENT '题目在本次闯关中的顺序',
  `selected_answers_json` JSON NOT NULL COMMENT '用户选择的答案',
  `correct_answers_json` JSON NOT NULL COMMENT '正确答案快照',
  `is_correct` BOOLEAN NOT NULL COMMENT '本题是否答对',
  `duration_ms` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本题答题用时（毫秒）',
  `answered_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '答题时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_answer_records_quiz_question` (`quiz_session_id`, `question_id`),
  KEY `idx_answer_records_quiz_order` (`quiz_session_id`, `question_order`),
  CONSTRAINT `fk_answer_records_quiz_session`
    FOREIGN KEY (`quiz_session_id`) REFERENCES `quiz_sessions` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='用户逐题作答记录';

CREATE TABLE IF NOT EXISTS `reports` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '复盘报告主键',
  `quiz_session_id` BIGINT UNSIGNED NOT NULL COMMENT '所属闯关记录',
  `accuracy` DECIMAL(5,2) NOT NULL COMMENT '本次正确率，范围 0.00-100.00',
  `mastered_points_json` JSON NOT NULL COMMENT '已掌握知识点',
  `weak_points_json` JSON NOT NULL COMMENT '薄弱知识点',
  `three_line_summary_json` JSON NOT NULL COMMENT '三句话总结',
  `advice_json` JSON NOT NULL COMMENT '后续学习建议',
  `share_quote` TEXT NOT NULL COMMENT '学习金句',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_reports_quiz_session` (`quiz_session_id`),
  CONSTRAINT `fk_reports_quiz_session`
    FOREIGN KEY (`quiz_session_id`) REFERENCES `quiz_sessions` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `chk_reports_accuracy`
    CHECK (`accuracy` >= 0 AND `accuracy` <= 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='AI 闯关复盘报告';
