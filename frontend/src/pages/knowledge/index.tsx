import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import fishai from '@/assets/fishai.svg'
import { getKnowledgeBases } from '@/services/api'
import type { KnowledgeBaseSummary } from '@/types/api'
import './index.scss'

export default function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeBaseSummary[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try { setItems(await getKnowledgeBases()) }
    catch (error) { Taro.showToast({ title: error instanceof Error ? error.message : '资料库加载失败', icon: 'none' }) }
    finally { setLoading(false); Taro.stopPullDownRefresh() }
  }
  useDidShow(() => { void load() })
  usePullDownRefresh(() => { void load() })

  return <View className='screen knowledge-screen'><View className='screen-body knowledge-body'>
    <View className='knowledge-head'><View><View className='knowledge-hero'><Text>资料分柜放，</Text><Text>找起来不迷路。</Text></View><View className='knowledge-sub'>{items.length} / 5 个知识库</View></View><Button className='knowledge-small-btn' onClick={() => Taro.navigateTo({ url: '/pages/knowledge-create/index' })}>＋ 新建</Button></View>
    {!loading && !items.length ? <View className='knowledge-empty'><Image src={fishai} /><View className='knowledge-empty-title'>资料柜还是空的</View><View className='knowledge-sub'>上传第一份文档，让鱼仔按你的资料出题。</View><Button className='primary-btn' onClick={() => Taro.navigateTo({ url: '/pages/knowledge-create/index' })}>＋ 新建知识库</Button></View> : items.map((item) => {
      const ready = item.ready_document_count > 0
      return <Button key={item.id} className={`knowledge-card ${ready ? '' : 'is-working'}`} onClick={() => Taro.navigateTo({ url: `/pages/knowledge-detail/index?id=${item.id}` })}>
        <Text className={`knowledge-badge ${ready ? '' : 'is-working'}`}>{ready ? '● 可用于出题' : '⟳ 等待资料就绪'}</Text><Text className='knowledge-card-title'>{item.name}</Text><Text className='knowledge-meta'>{item.document_count} 份文档 · {item.chunk_count} 个知识片段</Text><Text className='knowledge-card-foot'>{item.description || '鱼仔会按这柜资料帮你出题'}　›</Text>
      </Button>
    })}
  </View></View>
}
