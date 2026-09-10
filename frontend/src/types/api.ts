export type QuestionType = 'single' | 'multiple' | 'judge'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type InputSourceType = 'text' | 'url'
export type SourceScope = 'web' | 'private' | 'mixed'
export type GroundingMode = 'user_content' | 'web_search' | 'url_extract' | 'mixed' | 'private' | 'hybrid'
export type AcquisitionMethod = 'search_snippet' | 'user_url_extract' | 'search_result_extract' | 'private_document'

export interface GroundingSource {
  source_id: string
  title: string
  url: string
  site_name: string
  acquisition_method: AcquisitionMethod
  published_at?: string | null
  source_type?: 'web' | 'private_document'
  knowledge_base_id?: number | null
  document_id?: string | null
  location?: string | null
}

export interface Option {
  key: string
  text: string
}

export interface Question {
  id: string
  type: QuestionType
  stem: string
  options: Option[]
  answer: string[]
  explanation: string
  knowledge_point: string
  difficulty: Difficulty
  source_ids?: string[]
}

export interface Quiz {
  quiz_id: string
  title: string
  summary: string
  source_type: InputSourceType
  user_input: string
  questions: Question[]
  grounding_mode?: GroundingMode
  sources?: GroundingSource[]
  researched_at?: string | null
}

export type QuizTaskState = 'pending' | 'processing' | 'completed' | 'failed'

export interface QuizTaskStatus {
  task_id: string
  status: QuizTaskState
  quiz?: Quiz | null
  error_code?: number | null
  error_message?: string | null
}

export interface AnswerRecord {
  question_id: string
  selected_answers: string[]
  duration_ms: number
}

export interface AnswerResult extends AnswerRecord {
  correct_answers: string[]
  is_correct: boolean
}

export interface LearningReport {
  accuracy: number
  correct_count: number
  total_count: number
  xp_earned: number
  mastered_points: string[]
  weak_points: string[]
  answer_results: AnswerResult[]
  three_line_summary: string[]
  advice: string[]
  share_quote: string
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T | null
}

export interface UserSummary {
  id: number
  nickname: string
  avatar_url: string | null
  total_xp: number
}

export interface LoginResult {
  token: string
  user: UserSummary
}

export interface UserProfile extends UserSummary {
  quiz_count: number
  correct_count: number
  average_accuracy: number
}

export interface QuizHistoryItem {
  quiz_id: string
  title: string
  accuracy: number | null
  question_count: number
  correct_count: number | null
  xp_earned: number
  status: 'generated' | 'completed'
  created_at: string
}

export interface QuizHistoryPage {
  items: QuizHistoryItem[]
  total: number
  page: number
  page_size: number
}

export interface QuizHistoryDetail {
  quiz: Record<string, unknown>
  answer_records: Array<Record<string, unknown>>
  report: Record<string, unknown> | null
}

export type KnowledgeDocumentStatus = 'uploaded' | 'parsing' | 'chunking' | 'embedding' | 'ready' | 'failed' | 'deleting'

export interface KnowledgeDocument {
  document_id: string
  knowledge_base_id: number
  filename: string
  content_type: string
  size_bytes: number
  status: KnowledgeDocumentStatus
  error_code?: string | null
  error_message?: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseSummary {
  id: number
  name: string
  description?: string | null
  document_count: number
  ready_document_count: number
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseDetail extends KnowledgeBaseSummary {
  documents: KnowledgeDocument[]
}

export interface DocumentIngestionTask {
  task_id: string
  document_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  stage: 'uploaded' | 'parsing' | 'chunking' | 'embedding' | 'ready' | 'failed'
  error_code?: string | null
  error_message?: string | null
}

export interface DocumentUploadAccepted {
  document: KnowledgeDocument
  task: DocumentIngestionTask
}
