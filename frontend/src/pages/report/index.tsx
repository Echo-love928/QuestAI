import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import CoachNote from '@/components/CoachNote'
import { generateReport } from '@/services/api'
import type { LearningReport, Quiz } from '@/types/api'
import { learningStorage } from '@/utils/storage'

import './index.scss'

type LoadState = 'loading' | 'ready' | 'error'

export default function ReportPage() {
  const [quiz] = useState<Quiz | null>(() => learningStorage.getQuiz())
  const [report, setReport] = useState<LearningReport | null>(() => learningStorage.getReport())
  const [loadState, setLoadState] = useState<LoadState>(() => report ? 'ready' : 'loading')
  const [error, setError] = useState('')
  const [showWeakDetail, setShowWeakDetail] = useState(false)
  const requested = useRef(false)

  const loadReport = async () => {
    if (!quiz) return
    setLoadState('loading')
    setError('')
    try {
      const next = await generateReport({
        quiz_id: quiz.quiz_id,
        topic: quiz.title,
        questions: quiz.questions,
        answer_records: learningStorage.getAnswers()
      })
      learningStorage.saveReport(next)
      setReport(next)
      setLoadState('ready')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '报告生成失败，请稍后重试')
      setLoadState('error')
    }
  }

  useEffect(() => {
    if (!report && quiz && !requested.current) {
      requested.current = true
      void loadReport()
    }
  }, [])

  if (!quiz) {
    return <View className='screen'><View className='screen-body center'><Button className='primary-btn' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>返回首页</Button></View></View>
  }

  if (loadState === 'loading') {
    return (
      <View className='screen report-loading'><View className='screen-body center'><View className='app-bar'><Button className='icon-btn' onClick={() => Taro.navigateBack()}>←</Button><View className='progress-pill'>生成复盘</View></View><View className='report-loader'>80%</View><View className='loading-report-title'>鱼仔正在整理你的答题表现</View><View className='subcopy'>先算准得分，再把薄弱点说清楚。</View><CoachNote>报告里的正确率由程序计算，鱼仔只负责把建议讲明白。</CoachNote></View></View>
    )
  }

  if (loadState === 'error' || !report) {
    return (
      <View className='screen'><View className='screen-body error-report-body'><View className='app-bar'><Button className='icon-btn' onClick={() => Taro.navigateBack()}>←</Button><View /></View><View className='report-error-card'><View className='report-error-mark'>!</View><View className='report-error-title'>复盘暂时没生成出来</View><View className='report-error-copy'>{error}</View></View><Button className='primary-btn' onClick={loadReport}>重新生成报告</Button></View></View>
    )
  }

  const weakPoint = report.weak_points[0]

  if (showWeakDetail) {
    return (
      <View className='screen'>
        <View className='screen-body weak-body'>
          <View className='app-bar'><Button className='icon-btn' onClick={() => setShowWeakDetail(false)}>←</Button><Text className='bar-title'>红笔重点区</Text><View className='xp-pill'>{report.weak_points.length} 项</View></View>
          <View className='weak-card'>
            <Text className='question-tag'>最值得复习</Text>
            <View className='weak-title'>{weakPoint || '本次没有明显薄弱点'}</View>
            <View className='weak-copy'>{weakPoint ? `这部分在本次作答中出现了偏差。把“有资料支撑”和“结论绝对正确”分开理解，会更稳。` : '这次全部掌握，可以尝试更高难度的应用题。'}</View>
            <View className='compare-box'>
              <View className='compare-item'><Text className='compare-title'>已经做到</Text><Text>理解核心定义、识别主要流程、找到资料依据</Text></View>
              <View className='compare-item'><Text className='compare-title'>继续留意</Text><Text>检索完整性、模型理解偏差与能力边界</Text></View>
            </View>
            <CoachNote>{weakPoint ? '口诀：有依据，不等于零失误。' : '基础很稳，可以开始挑战应用场景。'}</CoachNote>
          </View>
          <View className='summary-card advice-card'><View className='summary-title'>建议下一步</View>{report.advice.map((item, index) => <View className='summary-line' key={item}><Text>{index + 1}.</Text><Text>{item}</Text></View>)}</View>
          <View className='action-stack weak-actions'><Button className='primary-btn' onClick={() => Taro.showToast({ title: '针对练习将在后续版本开放', icon: 'none' })}>针对练 2 题</Button><Button className='ghost-btn' onClick={() => setShowWeakDetail(false)}>返回报告</Button></View>
        </View>
      </View>
    )
  }

  const restart = () => {
    learningStorage.clear()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  return (
    <View className='screen'>
      <View className='screen-body report-body'>
        <View className='app-bar'><Button className='icon-btn' onClick={() => Taro.navigateBack()}>←</Button><Text className='bar-title'>本次复盘</Text><Button className='icon-btn' onClick={() => Taro.showToast({ title: '报告已保存在本机', icon: 'none' })}>···</Button></View>
        <View className='report-hero'>
          <View className='donut' style={{ background: `conic-gradient(var(--orange) 0 ${report.accuracy}%, var(--paper-deep) ${report.accuracy}% 100%)` }}><View className='donut-core'>{report.accuracy}%</View></View>
          <View className='hero-result'><View className='report-title'>{report.accuracy >= 80 ? '掌握得不错' : '再巩固一下'}</View><View className='report-copy'>{report.total_count} 题答对 {report.correct_count} 题。复盘已经按你的真实作答生成。</View></View>
        </View>
        <View className='mastery-grid'>
          <View className='mastery-card'><Text className='mastery-title'>✓ 已掌握 {report.mastered_points.length} 项</Text><Text className='mastery-copy'>{report.mastered_points.join('、') || '继续探索'}</Text></View>
          <View className='mastery-card weak'><Text className='mastery-title'>! 待巩固 {report.weak_points.length} 项</Text><Text className='mastery-copy'>{report.weak_points.join('、') || '暂无'}</Text></View>
        </View>
        <View className='summary-card'><View className='summary-title'>三句话带走</View>{report.three_line_summary.map((item, index) => <View className='summary-line' key={item}><Text>{index + 1}.</Text><Text>{item}</Text></View>)}</View>
        <View className='action-stack report-actions'>
          <Button className='secondary-btn' onClick={() => setShowWeakDetail(true)}>查看薄弱点 →</Button>
          <Button className='primary-btn' onClick={restart}>再来一关</Button>
        </View>
      </View>
    </View>
  )
}
