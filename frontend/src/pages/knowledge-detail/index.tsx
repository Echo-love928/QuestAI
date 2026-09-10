import { Button, Text, View } from '@tarojs/components'
import Taro, { getCurrentInstance, useDidShow, usePullDownRefresh, useUnload } from '@tarojs/taro'
import { useRef, useState } from 'react'
import { deleteKnowledgeBase, deleteKnowledgeDocument, getKnowledgeBase, reindexKnowledgeDocument } from '@/services/api'
import type { KnowledgeBaseDetail, KnowledgeDocument } from '@/types/api'
import './index.scss'

const ACTIVE = new Set(['uploaded', 'parsing', 'chunking', 'embedding'])
const statusText = { uploaded: '待处理', parsing: '解析中', chunking: '分块中', embedding: '向量化', ready: '就绪', failed: '失败', deleting: '删除中' }
const sizeText = (size: number) => size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)}MB` : `${Math.ceil(size / 1024)}KB`

export default function KnowledgeDetailPage() {
  const id = Number(getCurrentInstance().router?.params.id || 0)
  const [detail, setDetail] = useState<KnowledgeBaseDetail | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const load = async () => {
    try {
      const next = await getKnowledgeBase(id); setDetail(next); Taro.setNavigationBarTitle({ title: next.name })
      if (timer.current) clearTimeout(timer.current)
      if (next.documents.some((doc) => ACTIVE.has(doc.status))) timer.current = setTimeout(() => { void load() }, 8000)
    } catch (error) { Taro.showToast({ title: error instanceof Error ? error.message : '加载失败', icon: 'none' }) }
    finally { Taro.stopPullDownRefresh() }
  }
  useDidShow(() => { void load() }); usePullDownRefresh(() => { void load() }); useUnload(() => { if (timer.current) clearTimeout(timer.current) })
  const removeDocument = (doc: KnowledgeDocument) => Taro.showModal({ title: `删除“${doc.filename}”？`, content: '原文件和向量索引将一并删除，已完成的闯关记录仍会保留。', confirmColor: '#e84b3c' }).then(async (result) => { if (result.confirm) { await deleteKnowledgeDocument(id, doc.document_id); await load() } })
  const removeBase = () => Taro.showModal({ title: `删除“${detail?.name}”？`, content: '将删除原文件与索引，操作不可撤销；历史闯关仍保留。', confirmColor: '#e84b3c' }).then(async (result) => { if (result.confirm) { await deleteKnowledgeBase(id); await Taro.navigateBack() } })
  if (!detail) return <View className='screen knowledge-screen'><View className='screen-body knowledge-body'><View className='knowledge-empty-title'>鱼仔正在翻资料…</View></View></View>
  return <View className='screen knowledge-screen'><View className='screen-body knowledge-body'>
    <View className='knowledge-head'><Text className='knowledge-badge'>{detail.ready_document_count ? '● 索引就绪' : '⟳ 等待就绪'}</Text><Button className='knowledge-small-btn' onClick={() => Taro.navigateTo({ url: `/pages/knowledge-upload/index?id=${id}&name=${encodeURIComponent(detail.name)}` })}>＋ 上传资料</Button></View>
    <View className='knowledge-hero'><Text>{detail.document_count} 份资料</Text><Text>{detail.document_count > 0 && detail.ready_document_count === detail.document_count ? '鱼仔已经整理好。' : '鱼仔正在整理。'}</Text></View><View className='knowledge-sub'>{detail.chunk_count} 个知识片段 · 下拉可刷新状态</View>
    <View className='knowledge-panel'>{detail.documents.length ? detail.documents.map((doc) => <View className='knowledge-file' key={doc.document_id}><Text className='knowledge-file-icon'>{doc.filename.split('.').pop()?.toUpperCase()}</Text><View className='knowledge-file-copy'><Text className='knowledge-file-name'>{doc.filename}</Text><Text className='knowledge-file-detail'>{sizeText(doc.size_bytes)} · {doc.status === 'ready' ? `${doc.chunk_count} 个片段` : (doc.error_message || statusText[doc.status])}</Text></View><View className='knowledge-file-actions'><Text className={`knowledge-badge ${doc.status === 'failed' ? 'is-failed' : ACTIVE.has(doc.status) ? 'is-working' : ''}`}>{statusText[doc.status]}</Text>{doc.status === 'failed' && <Button className='knowledge-link' onClick={() => reindexKnowledgeDocument(id, doc.document_id).then(load)}>重试</Button>}<Button className='knowledge-link' onClick={() => removeDocument(doc)}>删除</Button></View></View>) : <View className='knowledge-sub'>还没有资料，先上传第一份文档吧。</View>}</View>
    <Button className='primary-btn' disabled={!detail.ready_document_count} onClick={() => Taro.reLaunch({ url: `/pages/index/index?scope=private&kb=${id}` })}>基于这里的资料出题 →</Button><Button className='ghost-btn knowledge-danger' onClick={removeBase}>删除知识库</Button>
  </View></View>
}
