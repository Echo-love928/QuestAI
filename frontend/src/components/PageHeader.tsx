import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { ReactNode } from 'react'

interface Props {
  title: string
  trailing?: ReactNode
}

export default function PageHeader({ title, trailing }: Props) {
  return (
    <View className='user-page-header'>
      <Button className='user-back' onClick={() => Taro.navigateBack()}>←</Button>
      <Text className='user-page-title'>{title}</Text>
      <View className='user-header-trailing'>{trailing}</View>
    </View>
  )
}
