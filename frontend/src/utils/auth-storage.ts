import Taro from '@tarojs/taro'

import type { UserSummary } from '@/types/api'

const TOKEN_KEY = 'ai_level_access_token'
const USER_KEY = 'ai_level_current_user'

export const authStorage = {
  getToken(): string | null {
    return Taro.getStorageSync(TOKEN_KEY) || null
  },
  getUser(): UserSummary | null {
    return Taro.getStorageSync(USER_KEY) || null
  },
  saveSession(token: string, user: UserSummary): void {
    // 只有微信重新登录完整成功后才替换旧会话，避免一次异常刷掉有效 token。
    Taro.setStorageSync(TOKEN_KEY, token)
    Taro.setStorageSync(USER_KEY, user)
  },
  saveUser(user: UserSummary): void {
    Taro.setStorageSync(USER_KEY, user)
  },
  clear(): void {
    Taro.removeStorageSync(TOKEN_KEY)
    Taro.removeStorageSync(USER_KEY)
  }
}
