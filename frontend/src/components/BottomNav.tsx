import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'

type NavKey = 'challenge' | 'library' | 'profile'

interface Props {
  active: NavKey
}

export default function BottomNav({ active }: Props) {
  const open = (key: NavKey) => {
    if (key === active) return
    if (key === 'challenge') {
      void Taro.reLaunch({ url: '/pages/index/index' })
      return
    }
    if (key === 'profile') {
      void Taro.navigateTo({ url: '/pages/profile/index' })
      return
    }
    void Taro.showToast({ title: '题库将在后续版本开放', icon: 'none' })
  }

  return (
    <View className='bottom-nav'>
      <Button className={active === 'challenge' ? 'bottom-nav-item is-active' : 'bottom-nav-item'} onClick={() => open('challenge')}><Text className='bottom-nav-icon'>✦</Text><Text>闯关</Text></Button>
      <Button className={active === 'library' ? 'bottom-nav-item is-active' : 'bottom-nav-item'} onClick={() => open('library')}><Text className='bottom-nav-icon'>▤</Text><Text>题库</Text></Button>
      <Button className={active === 'profile' ? 'bottom-nav-item is-active' : 'bottom-nav-item'} onClick={() => open('profile')}><Text className='bottom-nav-icon'>●</Text><Text>我的</Text></Button>
    </View>
  )
}
