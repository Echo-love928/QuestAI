-- AI闯关学习：异步题目生成任务
-- 适用版本：MySQL 8.0+

USE `AI-learn`;

CREATE TABLE IF NOT EXISTS `quiz_generation_tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务主键',
  `task_id` VARCHAR(64) NOT NULL COMMENT '不可预测的对外任务标识',
  `user_id` BIGINT UNSIGNED NULL COMMENT '所属用户；匿名任务为空',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending'
    COMMENT 'pending、processing、completed 或 failed',
  `request_json` JSON NOT NULL COMMENT '题目生成请求快照',
  `result_json` JSON NULL COMMENT '生成完成后的完整题库',
  `error_code` INT NULL COMMENT '安全的业务错误码',
  `error_message` VARCHAR(255) NULL COMMENT '可向用户展示的错误信息',
  `started_at` DATETIME(3) NULL COMMENT '开始处理时间',
  `completed_at` DATETIME(3) NULL COMMENT '完成或失败时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_quiz_generation_tasks_task_id` (`task_id`),
  KEY `idx_quiz_generation_tasks_user_created` (`user_id`, `created_at`),
  KEY `idx_quiz_generation_tasks_status_created` (`status`, `created_at`),
  CONSTRAINT `fk_quiz_generation_tasks_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `chk_quiz_generation_tasks_status`
    CHECK (`status` IN ('pending', 'processing', 'completed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='异步题目生成任务';
