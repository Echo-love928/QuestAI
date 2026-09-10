import { Button, Text, View } from '@tarojs/components'
import Taro, { getCurrentInstance } from '@tarojs/taro'
import { useState } from 'react'
import { uploadKnowledgeDocument } from '@/services/api'
import './index.scss'

const MAX_BYTES = 10 * 1024 * 1024
const EXTENSIONS = ['pdf', 'doc', 'docx', 'md']

export default function KnowledgeUploadPage() {
  const params = getCurrentInstance().router?.params || {}
  const id = Number(params.id || 0)
  const name = decodeURIComponent(params.name || '当前知识库')
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const chooseAndUpload = async () => {
    if (uploading) return
    try {
      const result = await Taro.chooseMessageFile({ count: 1, type: 'file', extension: EXTENSIONS })
      const file = result.tempFiles[0]
      if (!file || file.size > MAX_BYTES) { Taro.showToast({ title: '单个文件不能超过 10MB', icon: 'none' }); return }
      const extension = file.name.split('.').pop()?.toLowerCase()
      if (!extension || !EXTENSIONS.includes(extension)) { Taro.showToast({ title: '仅支持 PDF、DOC、DOCX、Markdown', icon: 'none' }); return }
      setUploading(true); setProgress(0)
      await uploadKnowledgeDocument(id, file.path, setProgress)
      await Taro.showToast({ title: '已进入处理队列', icon: 'success' })
      setTimeout(() => Taro.redirectTo({ url: `/pages/knowledge-detail/index?id=${id}` }), 500)
    } catch (error) {
      const message = error instanceof Error ? error.message : (typeof error === 'object' && error && 'errMsg' in error ? String(error.errMsg) : '')
      if (!message.includes('cancel')) Taro.showToast({ title: message || '上传失败', icon: 'none' })
    } finally { setUploading(false) }
  }
  return <View className='screen knowledge-screen'><View className='screen-body knowledge-body'>
    <View className='knowledge-hero'><Text>把资料交给鱼仔，</Text><Text>它会一页页读。</Text></View><View className='knowledge-sub'>本次上传到“{name}”</View>
    <Button className='knowledge-upload-box' onClick={chooseAndUpload}><Text className='knowledge-upload-icon'>📎</Text><Text>{uploading ? '正在上传…' : '选择聊天文件'}</Text><Text className='knowledge-sub'>PDF、DOC、DOCX、Markdown</Text></Button>
    {uploading && <View><View className='knowledge-progress'><View style={{ width: `${progress}%` }} /></View><View className='knowledge-sub'>上传进度 {progress}% · 完成后将在后台解析和向量化</View></View>}
    <View className='knowledge-rules'><Text>• 单个文件不超过 10MB</Text><Text>• PDF 需包含可复制文字，不支持扫描件 OCR</Text><Text>• 不支持加密或设有打开密码的 PDF</Text><Text>• 旧版 DOC 将由兼容解析服务读取</Text></View>
    <View className='knowledge-notice'>🔒 原文不会发送给联网搜索；仅命中的必要片段会交给 DeepSeek 生成题目。</View><Button className='primary-btn' disabled={uploading} onClick={chooseAndUpload}>选择并开始上传 →</Button>
  </View></View>
}
