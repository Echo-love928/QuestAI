import { Image, Text, View } from '@tarojs/components'

import fishai from '@/assets/fishai.svg'

export default function CoachNote({ children }: { children: string }) {
  return (
    <View className='coach-note'>
      <Image className='coach-fish' src={fishai} mode='aspectFit' />
      <Text>{children}</Text>
    </View>
  )
}

