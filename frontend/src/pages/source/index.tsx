import { Button, View, WebView } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { useState } from 'react'

export default function SourcePage() {
  const [url, setUrl] = useState('')

  useLoad((params) => {
    const candidate = decodeURIComponent(params.url || '')
    try {
      if (new URL(candidate).protocol === 'https:') setUrl(candidate)
    } catch {
      setUrl('')
    }
  })

  if (!url) return <View className='screen'><View className='screen-body center'><View className='empty-title'>这个来源链接无法打开</View><Button className='primary-btn' onClick={() => Taro.navigateBack()}>返回</Button></View></View>
  return <WebView src={url} />
}
