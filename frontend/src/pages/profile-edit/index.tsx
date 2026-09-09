import { Button, Image, Input, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import fishai from '@/assets/fishai.svg'
import PageHeader from '@/components/PageHeader'
import { updateUserProfile, uploadAvatar } from '@/services/api'
import { authStorage } from '@/utils/auth-storage'

import './index.scss'

export default function ProfileEditPage() {
  const cached = authStorage.getUser()
  const [nickname, setNickname] = useState(cached?.nickname || '学习者')
  const [avatar, setAvatar] = useState(cached?.avatar_url || '')
  const [pendingAvatar, setPendingAvatar] = useState('')
  const [saving, setSaving] = useState(false)

  const save = async () => {
    const cleaned = nickname.trim()
    if (!cleaned) {
      void Taro.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }
    if (saving) return
    setSaving(true)
    try {
      if (pendingAvatar) await uploadAvatar(pendingAvatar)
      const profile = await updateUserProfile({ nickname: cleaned })
      authStorage.saveUser(profile)
      await Taro.showToast({ title: '学习档案已保存', icon: 'success' })
      setTimeout(() => { void Taro.navigateBack() }, 450)
    } catch (error) {
      void Taro.showToast({ title: error instanceof Error ? error.message : '保存失败', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <View className='screen'>
      <View className='screen-body user-screen-body edit-profile-body'>
        <PageHeader title='编辑学习档案' trailing={<Button className='edit-save-mini' loading={saving} onClick={save}>保存</Button>} />
        <View className='user-heading'>让鱼仔<Text className='user-heading-mark'>认出你</Text></View>
        <View className='user-subcopy'>头像和昵称只用于展示你的学习记录。</View>
        <View className='avatar-editor'>
          <View className='avatar-editor-image'><Image src={pendingAvatar || avatar || fishai} mode='aspectFill' /></View>
          <Button
            className='avatar-change'
            openType='chooseAvatar'
            onChooseAvatar={(event) => {
              const next = event.detail.avatarUrl
              setPendingAvatar(next)
              setAvatar(next)
            }}
          >换个头像 ✦</Button>
        </View>
        <View className='edit-field'>
          <Text className='edit-label'>你的昵称</Text>
          <Input className='edit-input' type='nickname' maxlength={32} value={nickname} onInput={(event) => setNickname(event.detail.value)} />
          <Text className='edit-hint'>点击输入框可使用微信昵称，也可以自己填写。</Text>
        </View>
        <View className='edit-field'>
          <Text className='edit-label'>学习搭档</Text>
          <Input className='edit-input is-disabled' value='鱼仔' disabled />
          <Text className='edit-hint'>鱼仔会陪你出题、闯关和复盘。</Text>
        </View>
        <Button className='primary-btn edit-submit' loading={saving} disabled={saving} onClick={save}>保存修改 →</Button>
      </View>
    </View>
  )
}
