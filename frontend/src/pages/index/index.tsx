import { Button, Image, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import bookbuddy from '@/assets/bookbuddy.svg'
import bulbbuddy from '@/assets/bulbbuddy.svg'
import fishai from '@/assets/fishai.svg'
import pencilbuddy from '@/assets/pencilbuddy.svg'
import BrandBar from '@/components/BrandBar'
import BottomNav from '@/components/BottomNav'
import CoachNote from '@/components/CoachNote'
import StatusBar from '@/components/StatusBar'
import { ensureLogin } from '@/services/auth'
import { generateQuiz, getQuizHistory, getUserProfile } from '@/services/api'
import type { QuizHistoryItem, UserSummary } from '@/types/api'
import { authStorage } from '@/utils/auth-storage'
import { learningStorage } from '@/utils/storage'

import './index.scss'

const inspirations = [
  {
    title: 'RAG 基础概念',
    description: '检索、生成与应用边界',
    value: 'RAG 是什么？它和普通搜索有什么区别？',
    icon: bookbuddy
  },
  {
    title: '提示词工程',
    description: '角色、约束与输出格式',
    value: '怎样写出清晰、有效的大模型提示词？',
    icon: bulbbuddy
  }
]

type PageState = 'idle' | 'loading' | 'error'

export default function IndexPage() {
  const [input, setInput] = useState('')
  const [pageState, setPageState] = useState<PageState>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [user, setUser] = useState<UserSummary | null>(() => authStorage.getUser())
  const [recentRecords, setRecentRecords] = useState<QuizHistoryItem[]>([])

  useDidShow(() => {
    void ensureLogin().then(async () => {
      const [profile, history] = await Promise.all([getUserProfile(), getQuizHistory(1, 2)])
      setUser(profile)
      setRecentRecords(history.items.filter((item) => item.status === 'completed'))
      authStorage.saveUser(profile)
    }).catch(() => undefined)
  })

  const startGenerate = async () => {
    if (input.trim().length < 4 || pageState === 'loading') return
    setPageState('loading')
    setErrorMessage('')
    try {
      const quiz = await generateQuiz(input.trim())
      learningStorage.saveQuiz(quiz)
      await Taro.navigateTo({ url: '/pages/preview/index' })
      setPageState('idle')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '网络连接失败，请检查后重试')
      setPageState('error')
    }
  }

  const useInspiration = (value: string) => {
    setInput(value)
    Taro.showToast({ title: '已填入学习主题', icon: 'none' })
  }

  const showLater = (source: string) => {
    Taro.showToast({ title: `${source}导入将在后续版本开放`, icon: 'none' })
  }

  if (pageState === 'loading') {
    return (
      <View className='screen loading-screen'>
        <StatusBar />
        <View className='screen-body center'>
          <View className='loading-top'><Button className='icon-btn' onClick={() => setPageState('idle')}>×</Button><Text className='progress-pill'>约 12 秒</Text></View>
          <Image className='mascot-large' src={fishai} mode='aspectFit' />
          <View className='loading-title'>鱼仔正在认真出题</View>
          <View className='subcopy'>把内容拆成五块容易记住的知识。</View>
          <View className='pencil-loader'><View className='pencil' /></View>
          <View className='loading-list'>
            <View className='loading-step'><Text className='step-dot'>✓</Text><Text>读懂输入内容</Text></View>
            <View className='loading-step'><Text className='step-dot'>✓</Text><Text>找出核心知识点</Text></View>
            <View className='loading-step is-current'><Text className='step-dot'>✎</Text><Text>编写题目与讲解</Text></View>
          </View>
          <CoachNote>先别划走，题目马上从草稿纸里蹦出来。</CoachNote>
        </View>
      </View>
    )
  }

  if (pageState === 'error') {
    return (
      <View className='screen'>
        <StatusBar />
        <View className='screen-body error-body center'>
          <View className='app-bar'><Button className='icon-btn' onClick={() => setPageState('idle')}>←</Button><View /></View>
          <View className='error-poster'>
            <View className='error-mark'>!</View>
            <View className='error-title'>这次没生成出来</View>
            <View className='error-copy'>{errorMessage || '网络刚刚断开了，输入内容还在。重新连接后可以直接再试一次。'}</View>
          </View>
          <View className='action-stack'>
            <Button className='primary-btn' onClick={startGenerate}>重新生成</Button>
            <Button className='ghost-btn' onClick={() => setPageState('idle')}>返回修改内容</Button>
          </View>
          <CoachNote>不是你写得不对，内容没有丢。检查连接后再试一次。</CoachNote>
        </View>
      </View>
    )
  }

  return (
    <View className='screen'>
      <StatusBar />
      <View className='screen-body home-body'>
        <BrandBar trailing={<View className='xp-pill' onClick={() => Taro.navigateTo({ url: '/pages/profile/index' })}><Text className='star'>★</Text><Text>{user?.total_xp ?? 0} XP</Text></View>} />
        <View className='home-user-strip' onClick={() => Taro.navigateTo({ url: '/pages/profile/index' })}><Image src={user?.avatar_url || fishai} mode='aspectFill' /><Text>{user ? `${user.nickname}，和鱼仔继续闯关` : '鱼仔正在识别你的学习档案'}</Text><Text>›</Text></View>
        <View className='hero-copy home-one-liner'>
          <Text>{input.trim() ? '内容已就位，' : '输入想学的内容，'}</Text><View className='line-break' />
          <Text className='scribble'>{input.trim() ? '马上生成这组闯关题。' : '马上生成闯关题。'}</Text>
        </View>
        <View className='input-wrap'>
          <Textarea
            className='learning-input'
            value={input}
            maxlength={2000}
            placeholder='例如：我想弄懂 RAG 和普通搜索有什么区别'
            onInput={(event) => setInput(event.detail.value)}
          />
          <Text className='input-counter'>{input.length}/2000</Text>
        </View>
        <View className='source-row'>
          <Button className='source-chip is-active'>文本</Button>
          <Button className='source-chip' onClick={() => showLater('URL')}>URL</Button>
          <Button className='source-chip' onClick={() => showLater('文件')}>文件</Button>
          <Button className='source-chip' onClick={() => showLater('视频')}>视频</Button>
        </View>
        {input.trim().length >= 4 && <Button className='ghost-btn setting-btn'>⚙ 5 题 · 综合难度</Button>}
        <Button className='primary-btn generate-btn' disabled={input.trim().length < 4} onClick={startGenerate}>生成我的闯关 →</Button>

        {input.trim().length < 4 ? (
          <View className='inspiration-block'>
            <View className='inspiration-heading'><Text>没想好？试试这些</Text><Text className='muted'>点击填入</Text></View>
            <View className='inspiration-grid'>
              {inspirations.map((item) => (
                <Button key={item.title} className='inspiration-card' onClick={() => useInspiration(item.value)}>
                  <View className='cartoon-icon'><Image src={item.icon} mode='aspectFit' /></View>
                  <View className='inspiration-copy'><Text className='inspiration-title'>{item.title}</Text><Text className='inspiration-desc'>{item.description}</Text></View>
                </Button>
              ))}
            </View>
            {recentRecords.length > 0 && <View className='home-history'><View className='inspiration-heading'><Text>最近完成</Text><Text className='muted' onClick={() => Taro.navigateTo({ url: '/pages/history/index' })}>查看全部 →</Text></View>{recentRecords.map((record) => <Button className='home-history-card' key={record.quiz_id} onClick={() => Taro.navigateTo({ url: `/pages/history-detail/index?quizId=${encodeURIComponent(record.quiz_id)}` })}><View><Text>{record.title}</Text><Text>{record.correct_count}/{record.question_count} · +{record.xp_earned} XP</Text></View><Text>{record.accuracy}%</Text></Button>)}</View>}
          </View>
        ) : (
          <View className='ready-process'>
            <View className='process-buddy'><Image src={bookbuddy} /><Text>读取内容</Text></View><Text className='process-arrow'>→</Text>
            <View className='process-buddy'><Image src={pencilbuddy} /><Text>生成题目</Text></View><Text className='process-arrow'>→</Text>
            <View className='process-buddy'><Image src={fishai} /><Text>陪你闯关</Text></View>
          </View>
        )}
        <BottomNav active='challenge' />
      </View>
    </View>
  )
}
