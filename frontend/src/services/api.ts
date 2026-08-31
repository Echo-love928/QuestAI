import Taro from '@tarojs/taro'

import type { AnswerRecord, ApiResponse, LearningReport, Question, Quiz } from '@/types/api'

const API_BASE = process.env.TARO_APP_API_BASE

async function request<T>(options: Taro.request.Option): Promise<T> {
  try {
    const response = await Taro.request<ApiResponse<T>>({
      timeout: 60000,
      ...options,
      header: {
        'content-type': 'application/json',
        ...options.header
      }
    })
    const body = response.data
    if (response.statusCode < 200 || response.statusCode >= 300 || body.code !== 0 || !body.data) {
      throw new Error(body.message || '请求失败，请稍后重试')
    }
    return body.data
  } catch (error) {
    if (error instanceof Error) throw error
    throw new Error('网络连接失败，请检查后重试')
  }
}

export function generateQuiz(userInput: string, questionCount = 5): Promise<Quiz> {
  return request<Quiz>({
    url: `${API_BASE}/quiz/generate`,
    method: 'POST',
    data: {
      user_input: userInput,
      question_count: questionCount,
      difficulty: 'mixed'
    }
  })
}

export function generateReport(payload: {
  quiz_id: string
  topic: string
  questions: Question[]
  answer_records: AnswerRecord[]
}): Promise<LearningReport> {
  return request<LearningReport>({
    url: `${API_BASE}/report/generate`,
    method: 'POST',
    data: payload
  })
}

