import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import SourcePanel from '@/components/SourcePanel'
import type { Quiz } from '@/types/api'
import { learningStorage } from '@/utils/storage'

import './index.scss'

export default function PreviewPage() {
  const [quiz, setQuiz] = useState<Quiz | null>(() => learningStorage.getQuiz())

  useDidShow(() => setQuiz(learningStorage.getQuiz()))

  if (!quiz) {
    return (
      <View className='screen'><View className='screen-body center'><View className='empty-title'>还没有生成题目</View><Button className='primary-btn' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>返回首页</Button></View></View>
    )
  }

  const knowledgePoints = Array.from(new Set(quiz.questions.map((item) => item.knowledge_point))).slice(0, 3)

  return (
    <View className='screen preview-screen'>
      <View className='screen-body preview-body'>
        <View className='app-bar'><Button className='icon-btn' onClick={() => Taro.navigateBack()}>←</Button><View className='xp-pill'>新关卡</View></View>
        <View className='hero-copy'>题目就位，<View className='line-break' /><Text className='scribble'>开闯吧！</Text></View>
        <View className='topic-card'>
          <Text className='topic-stamp'>AI 已生成</Text>
          <View className='topic-title'>{quiz.title}</View>
          <View className='topic-summary'>{quiz.summary}</View>
          <View className='challenge-stats'>
            <View className='stat-box'><Text className='stat-value'>{quiz.questions.length}</Text><Text className='stat-label'>题目</Text></View>
            <View className='stat-box'><Text className='stat-value'>3 分</Text><Text className='stat-label'>预计用时</Text></View>
            <View className='stat-box'><Text className='stat-value'>混合</Text><Text className='stat-label'>难度</Text></View>
          </View>
        </View>
        <View className='roadmap'>
          {knowledgePoints.map((point, index) => (
            <View className='road-row' key={point}><Text className='road-num'>{index + 1}</Text><Text>{point}</Text></View>
          ))}
        </View>
        <SourcePanel mode={quiz.grounding_mode} sources={quiz.sources} researchedAt={quiz.researched_at} legacy={!quiz.grounding_mode} />
        <View className='action-stack preview-actions'>
          <Button className='primary-btn' onClick={() => Taro.navigateTo({ url: '/pages/quiz/index' })}>开始闯关！</Button>
          <Button className='ghost-btn' onClick={() => Taro.navigateBack()}>换一组题</Button>
        </View>
      </View>
    </View>
  )
}
