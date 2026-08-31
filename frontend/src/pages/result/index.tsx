import { Button, Image, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMemo, useState } from 'react'

import victory from '@/assets/victory.svg'
import CoachNote from '@/components/CoachNote'
import StatusBar from '@/components/StatusBar'
import type { AnswerRecord, Quiz } from '@/types/api'
import { learningStorage } from '@/utils/storage'

import './index.scss'

export default function ResultPage() {
  const [quiz] = useState<Quiz | null>(() => learningStorage.getQuiz())
  const [records] = useState<AnswerRecord[]>(() => learningStorage.getAnswers())

  const result = useMemo(() => {
    if (!quiz) return { correct: 0, total: 0, xp: 0, duration: 0 }
    const recordById = new Map(records.map((record) => [record.question_id, record]))
    const correct = quiz.questions.filter((question) => {
      const selected = recordById.get(question.id)?.selected_answers || []
      return selected.length === question.answer.length && selected.every((key) => question.answer.includes(key))
    }).length
    return {
      correct,
      total: quiz.questions.length,
      xp: correct * 10 + 10,
      duration: records.reduce((sum, record) => sum + record.duration_ms, 0)
    }
  }, [quiz, records])

  if (!quiz) {
    return <View className='screen'><StatusBar /><View className='screen-body center'><Button className='primary-btn' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>返回首页</Button></View></View>
  }

  const minutes = Math.floor(result.duration / 60000)
  const seconds = Math.floor((result.duration % 60000) / 1000)

  const restart = () => {
    learningStorage.clear()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  return (
    <View className='screen result-screen'>
      <StatusBar />
      <View className='screen-body result-body'>
        <View className='app-bar'><View /><View className='xp-pill'>本关完成</View></View>
        <View className='victory-scene'>
          <View className='victory-aura' />
          <Image className='victory-art' src={victory} mode='aspectFit' />
          <View className='victory-score'><Text className='victory-title'>通关啦！</Text><Text className='victory-count'>{result.correct} / {result.total}</Text></View>
        </View>
        <View className='reward-row'><Text className='reward-chip'>🏆 +{result.xp} XP</Text><Text className='reward-chip'>⏱ {minutes}分{String(seconds).padStart(2, '0')}秒</Text></View>
        <View className='result-title'>{quiz.title}完成</View>
        <View className='subcopy center'>{result.correct === result.total ? '全部答对，核心知识点已经稳稳拿下。' : '基本概念掌握得不错，应用边界还有一个小坑。'}</View>
        <CoachNote>比几分钟前多懂了一截。现在看看哪一块最值得复习。</CoachNote>
        <View className='action-stack result-actions'>
          <Button className='primary-btn' onClick={() => Taro.navigateTo({ url: '/pages/report/index' })}>看复盘报告</Button>
          <Button className='ghost-btn' onClick={restart}>再来一关</Button>
        </View>
      </View>
    </View>
  )
}

