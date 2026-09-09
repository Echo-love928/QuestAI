import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'

import type { GroundingMode, GroundingSource } from '@/types/api'

import './SourcePanel.scss'

const methodLabels = {
  search_snippet: '搜索摘要',
  user_url_extract: '原网页正文',
  search_result_extract: '补充网页正文'
} as const

interface SourcePanelProps {
  mode?: GroundingMode
  sources?: GroundingSource[]
  researchedAt?: string | null
  sourceIds?: string[]
  legacy?: boolean
  compact?: boolean
  title?: string
}

function isOpenableUrl(url: string): boolean {
  try {
    return url.startsWith('https://') && new URL(url).protocol === 'https:'
  } catch {
    return false
  }
}

export default function SourcePanel({ mode, sources = [], researchedAt, sourceIds, legacy = false, compact = false, title = '资料来源' }: SourcePanelProps) {
  const visibleSources = sourceIds?.length ? sources.filter((source) => sourceIds.includes(source.source_id)) : sources

  if (mode === 'user_content') return <View className='source-origin-note'>✎ 依据你提供的内容生成</View>
  if (!visibleSources.length) return legacy ? <View className='source-origin-note is-legacy'>历史记录未保存来源</View> : null

  const openSource = async (source: GroundingSource) => {
    if (!isOpenableUrl(source.url)) {
      await Taro.setClipboardData({ data: source.url })
      return
    }
    await Taro.navigateTo({ url: `/pages/source/index?url=${encodeURIComponent(source.url)}` })
  }

  const copySource = (url: string) => Taro.setClipboardData({ data: url })

  return <View className={`source-panel ${compact ? 'is-compact' : ''}`}>
    <View className='source-panel-head'><Text>{title} · {visibleSources.length} 份</Text>{researchedAt && <Text>{new Date(researchedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</Text>}</View>
    <View className='source-items'>{visibleSources.map((source) => <View className='source-item' key={source.source_id}>
      <View className='source-logo'>{source.site_name.slice(0, 1).toUpperCase()}</View>
      <View className='source-copy'><Text className='source-title'>{source.title}</Text><Text className='source-meta'>{source.site_name} · {methodLabels[source.acquisition_method]}</Text></View>
      <View className='source-actions'><Button onClick={() => openSource(source)}>打开</Button><Button onClick={() => copySource(source.url)}>复制</Button></View>
    </View>)}</View>
  </View>
}
