import type { PropsWithChildren } from 'react'
import { useLaunch } from '@tarojs/taro'

import { ensureLogin } from '@/services/auth'
import './app.scss'

export default function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    void ensureLogin().catch(() => {
      // 登录失败不阻塞原有匿名核心流程，用户功能页会显示可重试状态。
      if (process.env.NODE_ENV !== 'production') {
        console.warn('静默登录暂时失败，已保留匿名模式')
      }
    })
  })
  return children
}
