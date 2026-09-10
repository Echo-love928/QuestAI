-- AI闯关学习：用户私有知识库、文档和异步索引任务
-- 适用版本：MySQL 8.0+

USE `AI-learn`;

CREATE TABLE IF NOT EXISTS `knowledge_bases` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(30) NOT NULL,
  `description` VARCHAR(300) NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_knowledge_bases_user_updated` (`user_id`, `updated_at`),
  CONSTRAINT `fk_knowledge_bases_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='用户私有知识库';

CREATE TABLE IF NOT EXISTS `knowledge_documents` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `document_id` VARCHAR(64) NOT NULL,
  `knowledge_base_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `filename` VARCHAR(255) NOT NULL,
  `content_type` VARCHAR(128) NOT NULL,
  `extension` VARCHAR(12) NOT NULL,
  `size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256` CHAR(64) NOT NULL,
  `storage_key` VARCHAR(1024) NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'uploaded',
  `error_code` VARCHAR(64) NULL,
  `error_message` VARCHAR(255) NULL,
  `chunk_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `embedding_model` VARCHAR(64) NULL,
  `embedding_dimensions` SMALLINT UNSIGNED NULL,
  `index_version` INT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_knowledge_documents_document_id` (`document_id`),
  KEY `idx_knowledge_documents_kb_created` (`knowledge_base_id`, `created_at`),
  KEY `idx_knowledge_documents_user_status` (`user_id`, `status`),
  CONSTRAINT `fk_knowledge_documents_kb`
    FOREIGN KEY (`knowledge_base_id`) REFERENCES `knowledge_bases` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `fk_knowledge_documents_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `chk_knowledge_documents_status`
    CHECK (`status` IN ('uploaded', 'parsing', 'chunking', 'embedding', 'ready', 'failed', 'deleting'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='知识库原始文档及索引状态';

CREATE TABLE IF NOT EXISTS `document_ingestion_tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `task_id` VARCHAR(64) NOT NULL,
  `document_id` VARCHAR(64) NOT NULL,
  `knowledge_base_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `stage` VARCHAR(20) NOT NULL DEFAULT 'uploaded',
  `attempt` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  `error_code` VARCHAR(64) NULL,
  `error_message` VARCHAR(255) NULL,
  `started_at` DATETIME(3) NULL,
  `completed_at` DATETIME(3) NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_document_ingestion_tasks_task_id` (`task_id`),
  KEY `idx_document_ingestion_tasks_status_created` (`status`, `created_at`),
  KEY `idx_document_ingestion_tasks_document_created` (`document_id`, `created_at`),
  CONSTRAINT `fk_document_ingestion_tasks_document`
    FOREIGN KEY (`document_id`) REFERENCES `knowledge_documents` (`document_id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `fk_document_ingestion_tasks_kb`
    FOREIGN KEY (`knowledge_base_id`) REFERENCES `knowledge_bases` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `fk_document_ingestion_tasks_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT `chk_document_ingestion_tasks_status`
    CHECK (`status` IN ('pending', 'processing', 'completed', 'failed')),
  CONSTRAINT `chk_document_ingestion_tasks_stage`
    CHECK (`stage` IN ('uploaded', 'parsing', 'chunking', 'embedding', 'ready', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='文档异步索引任务';
