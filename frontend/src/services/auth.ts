import Taro from '@tarojs/taro'

import type { ApiResponse, LoginResult } from '@/types/api'
import { authStorage } from '@/utils/auth-storage'

const API_BASE = process.env.TARO_APP_API_BASE
let loginInFlight: Promise<LoginResult> | null = null

async function loginOnce(): Promise<LoginResult> {
  const loginResult = await Taro.login()
  if (!loginResult.code) throw new Error('微信登录凭证获取失败')
  const response = await Taro.request<ApiResponse<LoginResult>>({
    url: `${API_BASE}/user/login`,
    method: 'POST',
    timeout: 15000,
    header: { 'content-type': 'application/json' },
    data: { code: loginResult.code }
  })
  const body = response.data
  if (response.statusCode < 200 || response.statusCode >= 300 || body.code !== 0 || !body.data) {
    throw new Error(body.message || '登录失败，请稍后重试')
  }
  authStorage.saveSession(body.data.token, body.data.user)
  return body.data
}

export function ensureLogin(force = false): Promise<LoginResult> {
  const token = authStorage.getToken()
  const user = authStorage.getUser()
  if (!force && token && user) return Promise.resolve({ token, user })
  if (!loginInFlight) {
    loginInFlight = loginOnce().finally(() => {
      loginInFlight = null
    })
  }
  return loginInFlight
}
