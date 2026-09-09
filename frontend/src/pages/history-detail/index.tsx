import { Button, Text, View } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { useState } from 'react'

import PageHeader from '@/components/PageHeader'
import SourcePanel from '@/components/SourcePanel'
import { getQuizHistoryDetail } from '@/services/api'
import type { AnswerResult, GroundingMode, GroundingSource, LearningReport, Question, QuizHistoryDetail } from '@/types/api'

import './index.scss'

type LoadState = 'loading' | 'ready' | 'error'

interface StoredQuiz {
  quiz_id: string
  title: string
  question_count: number
  correct_count: number | null
  accuracy: number | null
  xp_earned: number
  status: string
  created_at: string
  questions: Question[]
  grounding_mode?: GroundingMode
  sources?: GroundingSource[]
  researched_at?: string | null
}

export default function HistoryDetailPage() {
  const [detail, setDetail] = useState<QuizHistoryDetail | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [message, setMessage] = useState('')
  const [quizId, setQuizId] = useState('')

  const load = async (id: string) => {
    setState('loading')
    try {
      setDetail(await getQuizHistoryDetail(id))
      setState('ready')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '闯关详情加载失败')
      setState('error')
    }
  }

  useLoad((params) => {
    const id = decodeURIComponent(params.quizId || '')
    setQuizId(id)
    if (id) void load(id)
    else {
      setMessage('缺少闯关编号')
      setState('error')
    }
  })

  if (state === 'loading') return <View className='screen'><View className='screen-body user-screen-body'><PageHeader title='闯关详情' /><View className='user-loading'><Text className='user-state-icon'>📖</Text><View className='user-state-title'>正在展开这页记录</View></View></View></View>
  if (state === 'error' || !detail) return <View className='screen'><View className='screen-body user-screen-body'><PageHeader title='闯关详情' /><View className='user-error'><Text className='user-state-icon'>?</Text><View className='user-state-title'>这页记录没找到</View><View className='user-state-copy'>{message}</View>{quizId && <Button className='primary-btn user-state-action' onClick={() => load(quizId)}>重新加载 →</Button>}</View></View></View>

  const quiz = detail.quiz as unknown as StoredQuiz
  const answers = detail.answer_records as unknown as AnswerResult[]
  const report = detail.report as unknown as LearningReport | null
  const questionById = new Map((quiz.questions || []).map((item) => [item.id, item]))

  return (
    <View className='screen'>
      <View className='screen-body user-screen-body history-detail-body'>
        <PageHeader title='闯关详情' trailing={<View className='xp-pill'>+{quiz.xp_earned} XP</View>} />
        <View className='history-detail-hero'><View className='history-detail-title'>{quiz.title}</View><View className='history-detail-meta'><Text>{quiz.status === 'completed' ? '已完成' : '待完成'}</Text><Text>{quiz.correct_count ?? 0} / {quiz.question_count} · {quiz.accuracy ?? '--'}%</Text></View></View>
        <SourcePanel mode={quiz.grounding_mode} sources={quiz.sources} researchedAt={quiz.researched_at} legacy={!quiz.grounding_mode} />
        <View className='detail-section-title'><Text>答题回看</Text><Text>共 {quiz.question_count} 题</Text></View>
        {answers.length ? answers.map((answer, index) => {
          const question = questionById.get(answer.question_id)
          return <View className={answer.is_correct ? 'history-answer is-correct' : 'history-answer is-wrong'} key={answer.question_id}><Text className='history-answer-title'>{answer.is_correct ? '✓' : '×'} 第 {index + 1} 题 · {question?.knowledge_point || '知识点'}</Text><Text className='history-answer-stem'>{question?.stem}</Text><Text>你的答案：{answer.selected_answers.join('、')}</Text>{!answer.is_correct && <Text>正确答案：{answer.correct_answers.join('、')}</Text>}<SourcePanel compact title='本题依据' mode={quiz.grounding_mode} sources={quiz.sources} sourceIds={question?.source_ids} legacy={!quiz.grounding_mode} /></View>
        }) : <View className='detail-pending'>这关还没有提交答案。</View>}
        {report && <><View className='detail-section-title'><Text>鱼仔复盘</Text></View><View className='history-report'>{report.three_line_summary?.map((line, index) => <Text key={line}>{index + 1}. {line}</Text>)}{report.advice?.[0] && <Text className='history-report-advice'>下一步：{report.advice[0]}</Text>}</View></>}
        <Button className='primary-btn detail-new-challenge' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>再学一个新主题 →</Button>
      </View>
    </View>
  )
}
