import { Image, Text, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import fishai from '@/assets/fishai.svg'

interface Props {
  trailing?: ReactNode
}

export default function BrandBar({ trailing }: Props) {
  return (
    <View className='app-bar'>
      <View className='brand'>
        <View className='brand-badge'><Image src={fishai} mode='aspectFit' /></View>
        <Text>AI闯关学习</Text>
      </View>
      {trailing ?? <View />}
    </View>
  )
}

