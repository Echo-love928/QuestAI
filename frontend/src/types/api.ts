export type QuestionType = 'single' | 'multiple' | 'judge'
export type Difficulty = 'easy' | 'medium' | 'hard'

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
}

export interface Quiz {
  quiz_id: string
  title: string
  summary: string
  source_type: 'text'
  user_input: string
  questions: Question[]
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

