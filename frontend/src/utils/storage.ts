import Taro from '@tarojs/taro'

import type { AnswerRecord, LearningReport, Quiz } from '@/types/api'

const QUIZ_KEY = 'ai_level_current_quiz'
const ANSWERS_KEY = 'ai_level_answer_records'
const REPORT_KEY = 'ai_level_report'

export const learningStorage = {
  saveQuiz(quiz: Quiz) {
    Taro.setStorageSync(QUIZ_KEY, quiz)
    Taro.removeStorageSync(ANSWERS_KEY)
    Taro.removeStorageSync(REPORT_KEY)
  },
  getQuiz(): Quiz | null {
    return Taro.getStorageSync(QUIZ_KEY) || null
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

