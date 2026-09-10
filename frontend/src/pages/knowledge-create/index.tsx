import { Button, Input, Text, Textarea, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'
import { createKnowledgeBase } from '@/services/api'
import './index.scss'

export default function KnowledgeCreatePage() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    if (!name.trim() || saving) return
    setSaving(true)
    try {
      const item = await createKnowledgeBase({ name: name.trim(), description: description.trim() || undefined })
      await Taro.redirectTo({ url: `/pages/knowledge-upload/index?id=${item.id}&name=${encodeURIComponent(item.name)}` })
    } catch (error) { Taro.showToast({ title: error instanceof Error ? error.message : '创建失败', icon: 'none' }) }
    finally { setSaving(false) }
  }
  return <View className='screen knowledge-screen'><View className='screen-body knowledge-body'>
    <View className='knowledge-hero'><Text>给这只资料柜</Text><Text>贴张标签。</Text></View><View className='knowledge-sub'>知识库名称和简介仅对你可见。</View>
    <View className='knowledge-panel'><View className='knowledge-label'>知识库名称</View><Input className='knowledge-input' maxlength={30} value={name} placeholder='例如：客服新人训练营' onInput={(e) => setName(e.detail.value)} /><View className='knowledge-label'>用途说明（选填）</View><Textarea className='knowledge-input knowledge-textarea' maxlength={300} value={description} placeholder='用于哪类学习、培训或考试？' onInput={(e) => setDescription(e.detail.value)} /></View>
    <Button className='primary-btn' disabled={!name.trim() || saving} onClick={submit}>{saving ? '正在创建…' : '创建并上传资料 →'}</Button><View className='knowledge-notice'>💡 一个知识库建议只放同一主题的资料，检索会更准确。</View>
  </View></View>
}
