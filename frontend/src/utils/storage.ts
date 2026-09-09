import Taro from '@tarojs/taro'

import type { AnswerRecord, LearningReport, Quiz } from '@/types/api'

const QUIZ_KEY = 'ai_level_current_quiz'
const ANSWERS_KEY = 'ai_level_answer_records'
const REPORT_KEY = 'ai_level_report'

function normalizeQuiz(value: unknown): Quiz | null {
  if (!value || typeof value !== 'object') return null
  const quiz = value as Quiz
  if (!quiz.quiz_id || !Array.isArray(quiz.questions)) return null
  return {
    ...quiz,
    source_type: quiz.source_type === 'url' ? 'url' : 'text',
    grounding_mode: quiz.grounding_mode || 'user_content',
    sources: Array.isArray(quiz.sources) ? quiz.sources : [],
    researched_at: quiz.researched_at || null,
    questions: quiz.questions.map((question) => ({
      ...question,
      source_ids: Array.isArray(question.source_ids) ? question.source_ids : []
    }))
  }
}

export const learningStorage = {
  saveQuiz(quiz: Quiz) {
    Taro.setStorageSync(QUIZ_KEY, quiz)
    Taro.removeStorageSync(ANSWERS_KEY)
    Taro.removeStorageSync(REPORT_KEY)
  },
  getQuiz(): Quiz | null {
    return normalizeQuiz(Taro.getStorageSync(QUIZ_KEY))
  },
  saveAnswers(records: AnswerRecord[]) {
    Taro.setStorageSync(ANSWERS_KEY, records)
  },
  getAnswers(): AnswerRecord[] {
    return Taro.getStorageSync(ANSWERS_KEY) || []
  },
  saveReport(report: LearningReport) {
    Taro.setStorageSync(REPORT_KEY, report)
  },
  getReport(): LearningReport | null {
    return Taro.getStorageSync(REPORT_KEY) || null
  },
  clear() {
    Taro.removeStorageSync(QUIZ_KEY)
    Taro.removeStorageSync(ANSWERS_KEY)
    Taro.removeStorageSync(REPORT_KEY)
  }
}
