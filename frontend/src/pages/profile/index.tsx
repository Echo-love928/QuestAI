import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import fishai from '@/assets/fishai.svg'
import BottomNav from '@/components/BottomNav'
import BrandBar from '@/components/BrandBar'
import { ensureLogin } from '@/services/auth'
import { getQuizHistory, getUserProfile } from '@/services/api'
import type { QuizHistoryItem, UserProfile } from '@/types/api'
import { authStorage } from '@/utils/auth-storage'

import './index.scss'

type LoadState = 'loading' | 'ready' | 'error'

const recordIcons = ['🧠', '🚀', '📚']

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [records, setRecords] = useState<QuizHistoryItem[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [message, setMessage] = useState('')

  const load = async () => {
    setState('loading')
    setMessage('')
    try {
      await ensureLogin()
      const [nextProfile, history] = await Promise.all([
        getUserProfile(),
        getQuizHistory(1, 2)
      ])
      setProfile(nextProfile)
      setRecords(history.items)
      authStorage.saveUser(nextProfile)
      setState('ready')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '学习档案连接失败')
      setState('error')
    }
  }

  useDidShow(() => { void load() })

  if (state === 'loading') {
    return <View className='screen'><View className='screen-body user-screen-body'><BrandBar /><View className='user-loading'><Text className='user-state-icon'>🐟</Text><View className='user-state-title'>鱼仔正在翻找档案</View><View className='user-state-copy'>成长记录马上就来。</View></View><BottomNav active='profile' /></View></View>
  }

  if (state === 'error' || !profile) {
    return <View className='screen'><View className='screen-body user-screen-body'><BrandBar /><View className='user-heading'>鱼仔暂时没认出你</View><View className='user-subcopy'>原有出题和答题功能仍可匿名使用。</View><View className='user-error'><Text className='user-state-icon'>📡</Text><View className='user-state-title'>学习档案连接失败</View><View className='user-state-copy'>{message || '检查网络后重新连接。'}</View><Button className='primary-btn user-state-action' onClick={load}>重新连接 →</Button><Button className='ghost-btn profile-anonymous' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>先去匿名闯关</Button></View><BottomNav active='profile' /></View></View>
  }

  return (
    <View className='screen'>
      <View className='screen-body user-screen-body profile-body'>
        <BrandBar trailing={<View className='xp-pill'><Text className='star'>★</Text><Text>{profile.total_xp} XP</Text></View>} />
        <View className='profile-card'>
          <Text className='profile-stamp'>学习中!</Text>
          <View className='profile-identity'>
            <View className='profile-avatar'><Image src={profile.avatar_url || fishai} mode='aspectFill' /></View>
            <View className='profile-copy'><View className='profile-name'>{profile.nickname}</View><View className='profile-motto'>和鱼仔一起，今天也学明白一点。</View><Button className='profile-edit' onClick={() => Taro.navigateTo({ url: '/pages/profile-edit/index' })}>编辑资料 ✎</Button></View>
          </View>
        </View>
        <View className='profile-stats'>
          <View className='profile-stat'><Text>{profile.quiz_count}</Text><Text>完成关卡</Text></View>
          <View className='profile-stat'><Text>{profile.correct_count}</Text><Text>累计答对</Text></View>
          <View className='profile-stat'><Text>{profile.average_accuracy}%</Text><Text>平均正确率</Text></View>
        </View>
        <Button className='profile-knowledge-entry' onClick={() => Taro.navigateTo({ url: '/pages/knowledge/index' })}><Text className='profile-record-icon'>🗂</Text><View><Text>我的资料库</Text><Text>上传私有文档，让鱼仔按你的资料出题</Text></View><Text>›</Text></Button>
        <View className='profile-section-title'><Text>最近闯关</Text><Button onClick={() => Taro.navigateTo({ url: '/pages/history/index' })}>查看全部 →</Button></View>
        {records.length ? records.map((record, index) => (
          <Button className='profile-record' key={record.quiz_id} onClick={() => Taro.navigateTo({ url: `/pages/history-detail/index?quizId=${encodeURIComponent(record.quiz_id)}` })}>
            <Text className='profile-record-icon'>{recordIcons[index % recordIcons.length]}</Text>
            <View className='profile-record-copy'><Text>{record.title}</Text><Text>{record.question_count} 题 · +{record.xp_earned} XP</Text></View>
            <Text className='profile-record-score'>{record.accuracy ?? '--'}%</Text>
          </Button>
        )) : <View className='profile-mini-empty'>还没有闯关脚印，先完成第一关吧。</View>}
        <BottomNav active='profile' />
      </View>
    </View>
  )
}
