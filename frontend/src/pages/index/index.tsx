import { Button, Image, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidShow, useUnload } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import bookbuddy from '@/assets/bookbuddy.svg'
import bulbbuddy from '@/assets/bulbbuddy.svg'
import fishai from '@/assets/fishai.svg'
import pencilbuddy from '@/assets/pencilbuddy.svg'
import BrandBar from '@/components/BrandBar'
import BottomNav from '@/components/BottomNav'
import CoachNote from '@/components/CoachNote'
import { ensureLogin } from '@/services/auth'
import { ApiError, generateQuiz, getQuizHistory, getUserProfile } from '@/services/api'
import type { CancellableRequest } from '@/services/api'
import type { InputSourceType, Quiz, QuizHistoryItem, UserSummary } from '@/types/api'
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
type LoadingStage = 'search' | 'extract' | 'verify' | 'generate'
type ErrorKind = 'url' | 'evidence' | 'ambiguous' | 'generic'

const RESEARCH_ERROR_CODES = {
  RESEARCH_URL_UNSAFE: 4101,
  RESEARCH_EVIDENCE_INSUFFICIENT: 4102,
  RESEARCH_AMBIGUOUS: 4103,
  RESEARCH_SEARCH_UNAVAILABLE: 5101,
  RESEARCH_URL_EXTRACT_UNAVAILABLE: 5102
} as const

const loadingCopy: Record<LoadingStage, { badge: string; title: string; copy: string }> = {
  search: { badge: '正在联网', title: '鱼仔正在翻最新资料', copy: '先认准领域，再比较新鲜、可靠的来源。' },
  extract: { badge: '读取网页', title: '鱼仔把网页装进资料袋', copy: '正在提取正文，广告和页面按钮不会拿来出题。' },
  verify: { badge: '核对依据', title: '鱼仔正在交叉核对', copy: '确认领域、更新时间和关键事实，再动笔出题。' },
  generate: { badge: '编写题目', title: '资料对上了，开始出题', copy: '每道题都会绑定这次找到的依据。' }
}

function isValidPublicUrl(value: string): boolean {
  try {
    const url = new URL(value.trim())
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname)
  } catch {
    return false
  }
}

export default function IndexPage() {
  const [input, setInput] = useState('')
  const [sourceType, setSourceType] = useState<InputSourceType>('text')
  const [pageState, setPageState] = useState<PageState>('idle')
  const [loadingStage, setLoadingStage] = useState<LoadingStage>('search')
  const [errorKind, setErrorKind] = useState<ErrorKind>('generic')
  const [errorMessage, setErrorMessage] = useState('')
  const [user, setUser] = useState<UserSummary | null>(() => authStorage.getUser())
  const [recentRecords, setRecentRecords] = useState<QuizHistoryItem[]>([])
  const requestRef = useRef<CancellableRequest<Quiz> | null>(null)
  const generationId = useRef(0)
  const stageTimers = useRef<Array<ReturnType<typeof setTimeout>>>([])

  const clearStageTimers = () => {
    stageTimers.current.forEach(clearTimeout)
    stageTimers.current = []
  }

  const cancelGeneration = () => {
    generationId.current += 1
    clearStageTimers()
    requestRef.current?.abort()
    requestRef.current = null
    setPageState('idle')
  }

  useUnload(cancelGeneration)
  useEffect(() => () => {
    clearStageTimers()
    requestRef.current?.abort()
  }, [])

  useDidShow(() => {
    void ensureLogin().then(async () => {
      const [profile, history] = await Promise.all([getUserProfile(), getQuizHistory(1, 2)])
      setUser(profile)
      setRecentRecords(history.items.filter((item) => item.status === 'completed'))
      authStorage.saveUser(profile)
    }).catch(() => undefined)
  })

  const startGenerate = async () => {
    const value = input.trim()
    const valid = sourceType === 'url' ? isValidPublicUrl(value) : value.length >= 4
    if (!valid || pageState === 'loading') {
      if (sourceType === 'url') Taro.showToast({ title: '请检查网址，需要完整的 HTTP / HTTPS 地址', icon: 'none' })
      return
    }
    const activeId = ++generationId.current
    clearStageTimers()
    setLoadingStage(sourceType === 'url' ? 'extract' : 'search')
    setPageState('loading')
    setErrorMessage('')
    setErrorKind('generic')
    stageTimers.current = [
      setTimeout(() => activeId === generationId.current && setLoadingStage('verify'), 2200),
      setTimeout(() => activeId === generationId.current && setLoadingStage('generate'), 4800)
    ]
    try {
      const operation = generateQuiz(value, 5, sourceType)
      requestRef.current = operation
      const quiz = await operation.promise
      if (activeId !== generationId.current) return
      learningStorage.saveQuiz(quiz)
      await Taro.navigateTo({ url: '/pages/preview/index' })
      setPageState('idle')
    } catch (error) {
      if (activeId !== generationId.current) return
      if (error instanceof ApiError) {
        if ([RESEARCH_ERROR_CODES.RESEARCH_URL_UNSAFE, RESEARCH_ERROR_CODES.RESEARCH_URL_EXTRACT_UNAVAILABLE].includes(error.code as 4101 | 5102)) setErrorKind('url')
        else if (error.code === RESEARCH_ERROR_CODES.RESEARCH_EVIDENCE_INSUFFICIENT) setErrorKind('evidence')
        else if (error.code === RESEARCH_ERROR_CODES.RESEARCH_AMBIGUOUS) setErrorKind('ambiguous')
      }
      setErrorMessage(error instanceof Error ? error.message : '网络连接失败，请检查后重试')
      setPageState('error')
    } finally {
      if (activeId === generationId.current) {
        clearStageTimers()
        requestRef.current = null
      }
    }
  }

  const useInspiration = (value: string) => {
    setSourceType('text')
    setInput(value)
    Taro.showToast({ title: '已填入学习主题', icon: 'none' })
  }

  const switchSource = (next: InputSourceType) => {
    if (pageState === 'loading') return
    setSourceType(next)
    setInput('')
  }

  const showLater = (source: string) => {
    Taro.showToast({ title: `${source}导入将在后续版本开放`, icon: 'none' })
  }

  if (pageState === 'loading') {
    const stage = loadingCopy[loadingStage]
    const steps = sourceType === 'url' ? ['检查网址', '提取网页', '核对依据', '生成题目'] : ['理解主题', '搜索资料', '核对依据', '生成题目']
    const currentStep = loadingStage === 'search' ? 1 : loadingStage === 'extract' ? 1 : loadingStage === 'verify' ? 2 : 3
    return (
      <View className='screen loading-screen'>
        <View className='screen-body center'>
          <View className='loading-top'><Button className='icon-btn' onClick={cancelGeneration}>×</Button><Text className='progress-pill'>{stage.badge}</Text></View>
          <Image className='mascot-large' src={fishai} mode='aspectFit' />
          <View className='loading-title'>{stage.title}</View>
          <View className='subcopy'>{stage.copy}</View>
          <View className='research-route'>{steps.slice(0, 3).map((step, index) => <View key={step} className={`route-stop ${index < currentStep ? 'is-done' : ''} ${index === currentStep ? 'is-current' : ''}`}><Text>{index < currentStep ? '✓' : index === currentStep ? '⌕' : '□'}</Text><Text>{step}</Text></View>)}</View>
          <View className='research-ticket'><Text className='research-ticket-title'>{sourceType === 'url' ? '正在读取你提供的网页' : `正在查：${input.slice(0, 32)}`}</Text><Text>鱼仔只会使用本次找到并核对过的资料，不会让旧知识抢答。</Text></View>
          <View className='loading-list'>
            {steps.map((step, index) => <View key={step} className={`loading-step ${index === currentStep ? 'is-current' : ''}`}><Text className='step-dot'>{index < currentStep ? '✓' : index === currentStep ? '⌕' : index + 1}</Text><Text>{step}</Text></View>)}
          </View>
          <CoachNote>先找对资料再出题，来源能对上才准许继续。</CoachNote>
        </View>
      </View>
    )
  }

  if (pageState === 'error') {
    const errorView = {
      url: { mark: '↗', title: '这个网址暂时读不到', note: '检查开头和访问权限，或改用关键词搜索。' },
      evidence: { mark: '?', title: '还缺一块关键资料', note: '补充更明确的主题、所属领域或原始内容。' },
      ambiguous: { mark: '≋', title: '这个主题有多种含义', note: '补充所属领域后，鱼仔再继续查资料。' },
      generic: { mark: '!', title: '这次没生成出来', note: '输入内容还在，稍后可以直接重试。' }
    }[errorKind]
    return (
      <View className='screen'>
        <View className='screen-body error-body center'>
          <View className='app-bar'><Button className='icon-btn' onClick={() => setPageState('idle')}>←</Button><View /></View>
          <View className={`error-poster is-${errorKind}`}>
            <View className='error-mark'>{errorView.mark}</View>
            <View className='error-title'>{errorView.title}</View>
            <View className='error-copy'>{errorMessage || errorView.note}</View>
          </View>
          <View className='recovery-tip'>{errorView.note}<Text> 原输入已保留。</Text></View>
          <View className='action-stack'>
            {errorKind === 'url' ? <Button className='primary-btn' onClick={() => setPageState('idle')}>检查网址</Button> : <Button className='primary-btn' onClick={startGenerate}>重新获取资料</Button>}
            <Button className='ghost-btn' onClick={() => setPageState('idle')}>返回修改内容</Button>
          </View>
          <CoachNote>资料不够时不会偷偷退回模型旧知识。</CoachNote>
        </View>
      </View>
    )
  }

  const inputValid = sourceType === 'url' ? isValidPublicUrl(input) : input.trim().length >= 4

  return (
    <View className='screen'>
      <View className='screen-body home-body'>
        <BrandBar trailing={<View className='xp-pill' onClick={() => Taro.navigateTo({ url: '/pages/profile/index' })}><Text className='star'>★</Text><Text>{user?.total_xp ?? 0} XP</Text></View>} />
        <View className='home-user-strip' onClick={() => Taro.navigateTo({ url: '/pages/profile/index' })}><Image src={user?.avatar_url || fishai} mode='aspectFill' /><Text>{user ? `${user.nickname}，和鱼仔继续闯关` : '鱼仔正在识别你的学习档案'}</Text><Text>›</Text></View>
        <View className='hero-copy home-one-liner'>
          <Text>{sourceType === 'url' ? (input.trim() ? '网页已收到，' : '粘贴学习网页，') : (input.trim() ? '内容已就位，' : '输入想学的内容，')}</Text><View className='line-break' />
          <Text className='scribble'>{sourceType === 'url' ? '读完再为你出题。' : (input.trim() ? '马上生成这组闯关题。' : '马上生成闯关题。')}</Text>
        </View>
        <View className='input-wrap'>
          <Textarea
            className='learning-input'
            value={input}
            maxlength={2000}
            placeholder={sourceType === 'url' ? '粘贴公开网页地址，例如：https://docs.example.com/guide' : '例如：我想弄懂 RAG 和普通搜索有什么区别'}
            onInput={(event) => setInput(event.detail.value)}
          />
          <Text className='input-counter'>{sourceType === 'url' ? '公开网页' : `${input.length}/2000`}</Text>
        </View>
        <View className='source-row'>
          <Button className={`source-chip ${sourceType === 'text' ? 'is-active' : ''}`} onClick={() => switchSource('text')}>文本</Button>
          <Button className={`source-chip ${sourceType === 'url' ? 'is-active' : ''}`} onClick={() => switchSource('url')}>URL</Button>
          <Button className='source-chip' onClick={() => showLater('文件')}>文件</Button>
          <Button className='source-chip' onClick={() => showLater('视频')}>视频</Button>
        </View>
        {sourceType === 'url' && <View className='url-hint'>↗ 支持公开的 HTTP / HTTPS 网页，不访问登录页或内网页面</View>}
        {inputValid && <Button className='ghost-btn setting-btn'>⚙ 5 题 · 综合难度</Button>}
        <Button className='primary-btn generate-btn' disabled={!inputValid} onClick={startGenerate}>{sourceType === 'url' ? '读取网页并生成 →' : '生成我的闯关 →'}</Button>

        {!inputValid ? (
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
            <View className='process-buddy'><Image src={bookbuddy} /><Text>{sourceType === 'url' ? '提取网页' : '搜索资料'}</Text></View><Text className='process-arrow'>→</Text>
            <View className='process-buddy'><Image src={pencilbuddy} /><Text>核对依据</Text></View><Text className='process-arrow'>→</Text>
            <View className='process-buddy'><Image src={fishai} /><Text>陪你闯关</Text></View>
          </View>
        )}
        <BottomNav active='challenge' />
      </View>
    </View>
  )
}
