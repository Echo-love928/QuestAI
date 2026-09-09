import Taro from '@tarojs/taro'

import type {
  AnswerRecord,
  ApiResponse,
  InputSourceType,
  LearningReport,
  Question,
  Quiz,
  QuizTaskStatus,
  QuizHistoryDetail,
  QuizHistoryPage,
  UserProfile
} from '@/types/api'
import { ensureLogin } from '@/services/auth'
import { authStorage } from '@/utils/auth-storage'

const API_BASE = process.env.TARO_APP_API_BASE

interface RequestOptions {
  allowAnonymous?: boolean
  retryAuth?: boolean
  suppressAuth?: boolean
  onTask?: (task: ReturnType<typeof Taro.request>) => void
}

export class ApiError extends Error {
  constructor(public readonly code: number, message: string, public readonly statusCode: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  options: Taro.request.Option,
  behavior: RequestOptions = {}
): Promise<T> {
  try {
    let token = behavior.suppressAuth ? null : authStorage.getToken()
    if (!token && !behavior.suppressAuth && !behavior.allowAnonymous) {
      await ensureLogin()
      token = authStorage.getToken()
    }
    const requestTask = Taro.request<ApiResponse<T>>({
      timeout: 60000,
      ...options,
      header: {
        'content-type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.header
      }
    })
    behavior.onTask?.(requestTask)
    const response = await requestTask
    const body = response.data
    if (response.statusCode === 401 && token && behavior.retryAuth !== false) {
      try {
        await ensureLogin(true)
        return request<T>(options, { ...behavior, retryAuth: false })
      } catch (loginError) {
        if (behavior.allowAnonymous) {
          return request<T>(options, {
            ...behavior,
            retryAuth: false,
            suppressAuth: true
          })
        }
        throw loginError
      }
    }
    if (response.statusCode < 200 || response.statusCode >= 300 || body.code !== 0 || !body.data) {
      throw new ApiError(body.code, body.message || '请求失败，请稍后重试', response.statusCode)
    }
    return body.data
  } catch (error) {
    if (error instanceof Error) throw error
    throw new Error('网络连接失败，请检查后重试')
  }
}

export interface CancellableRequest<T> {
  promise: Promise<T>
  abort: () => void
}

export function generateQuiz(userInput: string, questionCount = 5, sourceType: InputSourceType = 'text'): CancellableRequest<Quiz> {
  let requestTask: ReturnType<typeof Taro.request> | null = null
  let aborted = false
  const promise = request<Quiz>(
    {
      url: `${API_BASE}/quiz/generate`,
      method: 'POST',
      data: {
        user_input: userInput,
        source_type: sourceType,
        question_count: questionCount,
        difficulty: 'mixed'
      }
    },
    {
      allowAnonymous: true,
      onTask: (task) => {
        requestTask = task
        if (aborted) task.abort()
      }
    }
  )
  return {
    promise,
    abort: () => {
      aborted = true
      if (requestTask) requestTask.abort()
    }
  }
}

export function createQuizTask(
  userInput: string,
  questionCount = 5,
  sourceType: InputSourceType = 'text'
): Promise<QuizTaskStatus> {
  return request<QuizTaskStatus>(
    {
      url: `${API_BASE}/quiz/tasks`,
      method: 'POST',
      data: {
        user_input: userInput,
        source_type: sourceType,
        question_count: questionCount,
        difficulty: 'mixed'
      }
    },
    { allowAnonymous: true }
  )
}

export function getQuizTask(taskId: string): Promise<QuizTaskStatus> {
  return request<QuizTaskStatus>(
    {
      url: `${API_BASE}/quiz/tasks/${encodeURIComponent(taskId)}`,
      method: 'GET'
    },
    { allowAnonymous: true }
  )
}

export function generateReport(payload: {
  quiz_id: string
  topic: string
  questions: Question[]
  answer_records: AnswerRecord[]
}): Promise<LearningReport> {
  return request<LearningReport>(
    {
      url: `${API_BASE}/report/generate`,
      method: 'POST',
      data: payload
    },
    { allowAnonymous: true }
  )
}

export function getUserProfile(): Promise<UserProfile> {
  return request<UserProfile>({ url: `${API_BASE}/user/profile`, method: 'GET' })
}

export function updateUserProfile(payload: {
  nickname?: string
  avatar_url?: string
}): Promise<UserProfile> {
  return request<UserProfile>({
    url: `${API_BASE}/user/profile`,
    method: 'PUT',
    data: payload
  })
}

export function getQuizHistory(page = 1, pageSize = 10): Promise<QuizHistoryPage> {
  return request<QuizHistoryPage>({
    url: `${API_BASE}/user/quizzes?page=${page}&page_size=${pageSize}`,
    method: 'GET'
  })
}

export function getQuizHistoryDetail(quizId: string): Promise<QuizHistoryDetail> {
  return request<QuizHistoryDetail>({
    url: `${API_BASE}/user/quizzes/${encodeURIComponent(quizId)}`,
    method: 'GET'
  })
}

async function uploadAvatarAttempt(filePath: string, retryAuth: boolean): Promise<UserProfile> {
  if (!authStorage.getToken()) await ensureLogin()
  const activeToken = authStorage.getToken()
  const response = await Taro.uploadFile({
    url: `${API_BASE}/user/avatar`,
    filePath,
    name: 'file',
    header: activeToken ? { Authorization: `Bearer ${activeToken}` } : {}
  })
  const body = JSON.parse(response.data) as ApiResponse<UserProfile>
  if (response.statusCode === 401 && retryAuth) {
    await ensureLogin(true)
    return uploadAvatarAttempt(filePath, false)
  }
  if (response.statusCode < 200 || response.statusCode >= 300 || !body.data) {
    throw new Error(body.message || '头像上传失败')
  }
  authStorage.saveUser(body.data)
  return body.data
}

export function uploadAvatar(filePath: string): Promise<UserProfile> {
  return uploadAvatarAttempt(filePath, true)
}
