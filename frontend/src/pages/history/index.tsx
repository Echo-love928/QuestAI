import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import fishai from '@/assets/fishai.svg'
import BottomNav from '@/components/BottomNav'
import PageHeader from '@/components/PageHeader'
import StatusBar from '@/components/StatusBar'
import { getQuizHistory } from '@/services/api'
import type { QuizHistoryItem } from '@/types/api'

import './index.scss'

type Filter = 'all' | 'completed' | 'generated'
type LoadState = 'loading' | 'ready' | 'error'
const icons = ['🧠', '🪐', '📚', '🚀']

export default function HistoryPage() {
  const [items, setItems] = useState<QuizHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<Filter>('all')
  const [state, setState] = useState<LoadState>('loading')
  const [message, setMessage] = useState('')

  const load = async (nextPage = 1) => {
    if (nextPage === 1) setState('loading')
    setMessage('')
    try {
      const result = await getQuizHistory(nextPage, 10)
      setItems((current) => nextPage === 1 ? result.items : [...current, ...result.items])
      setTotal(result.total)
      setPage(nextPage)
      setState('ready')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '闯关记录加载失败')
      setState('error')
    } finally {
      Taro.stopPullDownRefresh()
    }
  }

  useDidShow(() => { void load() })
  usePullDownRefresh(() => { void load() })

  const counts = useMemo(() => ({
    completed: items.filter((item) => item.status === 'completed').length,
    generated: items.filter((item) => item.status === 'generated').length
  }), [items])
  const visible = items.filter((item) => filter === 'all' || item.status === filter)

  return (
    <View className='screen'>
      <StatusBar />
      <View className='screen-body user-screen-body history-body'>
        <PageHeader title='我的闯关' />
        <View className='user-heading'>学过的，都<Text className='user-heading-mark'>算数。</Text></View>
        <View className='user-subcopy'>共留下 {total} 个关卡脚印，鱼仔替你收好了。</View>
        {state === 'loading' ? <View className='user-loading'><Text className='user-state-icon'>🐟</Text><View className='user-state-title'>正在翻闯关册</View></View> : state === 'error' ? <View className='user-error'><Text className='user-state-icon'>📡</Text><View className='user-state-title'>记录暂时没加载出来</View><View className='user-state-copy'>{message}</View><Button className='primary-btn user-state-action' onClick={() => load()}>重新加载 →</Button></View> : items.length === 0 ? <View className='user-empty'><View className='history-empty-fish'><Image src={fishai} mode='aspectFit' /><Text>还空着呢!</Text></View><View className='user-state-title'>暂时没有闯关记录</View><View className='user-state-copy'>输入一段想学的内容，鱼仔马上给你变成一组题。</View><Button className='primary-btn user-state-action' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>去生成第一关 →</Button></View> : <>
          <View className='history-filters'>
            <Button className={filter === 'all' ? 'history-filter is-active' : 'history-filter'} onClick={() => setFilter('all')}>全部 {total}</Button>
            <Button className={filter === 'completed' ? 'history-filter is-active' : 'history-filter'} onClick={() => setFilter('completed')}>已完成 {counts.completed}</Button>
            <Button className={filter === 'generated' ? 'history-filter is-active' : 'history-filter'} onClick={() => setFilter('generated')}>未完成 {counts.generated}</Button>
          </View>
          {visible.map((record, index) => <Button className='history-record' key={record.quiz_id} onClick={() => Taro.navigateTo({ url: `/pages/history-detail/index?quizId=${encodeURIComponent(record.quiz_id)}` })}><Text className='history-record-icon'>{icons[index % icons.length]}</Text><View className='history-record-copy'><Text>{record.title}</Text><Text>{record.correct_count ?? 0}/{record.question_count} · +{record.xp_earned} XP · {record.status === 'completed' ? '已完成' : '待完成'}</Text></View><Text className='history-score'>{record.accuracy ?? '--'}%</Text></Button>)}
          {visible.length === 0 && <View className='history-filter-empty'>这个分类暂时没有记录。</View>}
          {items.length < total ? <Button className='ghost-btn history-more' onClick={() => load(page + 1)}>再翻一页</Button> : <View className='history-end'>已经到底啦 · 共 {total} 关</View>}
        </>}
        <BottomNav active='profile' />
      </View>
    </View>
  )
}
