import { Text, View } from '@tarojs/components'

export default function StatusBar() {
  return (
    <View className='status-bar'>
      <Text>9:41</Text>
      <Text className='status-icons'>● ◒ ▰</Text>
    </View>
  )
}

