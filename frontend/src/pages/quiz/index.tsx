import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMemo, useRef, useState } from 'react'

import StatusBar from '@/components/StatusBar'
import type { AnswerRecord, Question, Quiz } from '@/types/api'
import { learningStorage } from '@/utils/storage'

import './index.scss'

const typeLabels: Record<Question['type'], string> = {
  single: '单选',
  multiple: '多选',
  judge: '判断'
}

const difficultyLabels: Record<Question['difficulty'], string> = {
  easy: '基础',
  medium: '应用',
  hard: '进阶'
}

function isAnswerCorrect(question: Question, selected: string[]): boolean {
  return selected.length === question.answer.length && selected.every((key) => question.answer.includes(key))
}

export default function QuizPage() {
  const [quiz] = useState<Quiz | null>(() => learningStorage.getQuiz())
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedById, setSelectedById] = useState<Record<string, string[]>>({})
  const [submittedById, setSubmittedById] = useState<Record<string, boolean>>({})
  const [records, setRecords] = useState<AnswerRecord[]>([])
  const startedAt = useRef(Date.now())

  const correctCount = useMemo(() => {
    if (!quiz) return 0
    return quiz.questions.filter((question) => submittedById[question.id] && isAnswerCorrect(question, selectedById[question.id] || [])).length
  }, [quiz, selectedById, submittedById])

  if (!quiz) {
    return <View className='screen'><StatusBar /><View className='screen-body center'><View className='missing-copy'>题目走丢了，请重新生成。</View><Button className='primary-btn' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>返回首页</Button></View></View>
  }

  const question = quiz.questions[currentIndex]
  const selected = selectedById[question.id] || []
  const submitted = Boolean(submittedById[question.id])
  const correct = submitted && isAnswerCorrect(question, selected)
  const progress = Math.round(((currentIndex + 1) / quiz.questions.length) * 100)

  const choose = (key: string) => {
    if (submitted) return
    if (question.type === 'multiple') {
      setSelectedById((current) => {
        const previous = current[question.id] || []
        const next = previous.includes(key) ? previous.filter((item) => item !== key) : [...previous, key]
        return { ...current, [question.id]: next }
      })
      return
    }
    setSelectedById((current) => ({ ...current, [question.id]: [key] }))
  }

  const submitOrContinue = async () => {
    if (!selected.length) return
    if (!submitted) {
      const record: AnswerRecord = {
        question_id: question.id,
        selected_answers: selected,
        duration_ms: Math.max(0, Date.now() - startedAt.current)
      }
      setRecords((current) => [...current.filter((item) => item.question_id !== question.id), record])
      setSubmittedById((current) => ({ ...current, [question.id]: true }))
      return
    }
    if (currentIndex < quiz.questions.length - 1) {
      setCurrentIndex((index) => index + 1)
      startedAt.current = Date.now()
      return
    }
    learningStorage.saveAnswers(records)
    await Taro.redirectTo({ url: '/pages/result/index' })
  }

  const goPrevious = () => {
    if (currentIndex === 0) return
    setCurrentIndex((index) => index - 1)
  }

  const optionClass = (key: string) => {
    const classes = ['option']
    if (selected.includes(key)) classes.push('is-selected')
    if (submitted && question.answer.includes(key)) classes.push('is-correct')
    if (submitted && selected.includes(key) && !question.answer.includes(key)) classes.push('is-wrong')
    return classes.join(' ')
  }

  return (
    <View className='screen quiz-screen'>
      <StatusBar />
      <View className='screen-body quiz-body'>
        <View className='quiz-top'>
          <Button className='quiz-close' onClick={() => Taro.showModal({ title: '退出闯关？', content: '当前答题进度不会保存。', success: (res) => res.confirm && Taro.navigateBack() })}>×</Button>
          <View className='quiz-head-center'>
            <Text>第 {currentIndex + 1} / {quiz.questions.length} 题</Text>
            <View className='progress-track'>
              <View className='progress-fill' style={{ width: `${progress}%` }} />
              <View className='map-nodes'>
                {quiz.questions.map((item, index) => (
                  <View key={item.id} className={`map-node ${submittedById[item.id] ? 'done' : ''} ${index === currentIndex ? 'current' : ''}`}>
                    {submittedById[item.id] ? (isAnswerCorrect(item, selectedById[item.id] || []) ? '✓' : '×') : index + 1}
                  </View>
                ))}
              </View>
            </View>
          </View>
          <View className='quiz-xp'>{correctCount * 10} XP</View>
        </View>
        <View className='quiz-meta'><Text>第 {currentIndex + 1} 关 / 共 {quiz.questions.length} 关</Text><Text>答对 {correctCount} 题</Text></View>
        <View className='question-card'>
          <View className='question-kicker'><Text className='question-tag'>{typeLabels[question.type]} · {difficultyLabels[question.difficulty]}</Text><Text className='question-count'>{question.knowledge_point}</Text></View>
          <View className='question-title'>{question.stem}</View>
        </View>
        <View className='answer-list'>
          {question.options.map((option) => (
            <Button key={option.key} className={optionClass(option.key)} onClick={() => choose(option.key)}>
              <Text>{option.text}</Text>
              {submitted && selected.includes(option.key) && <Text className='answer-mark'>{question.answer.includes(option.key) ? '你的答案' : '你的'}</Text>}
              {submitted && question.answer.includes(option.key) && !selected.includes(option.key) && <Text className='answer-mark'>正解</Text>}
            </Button>
          ))}
        </View>

        {!submitted ? (
          <View className='quiz-hint'>{question.type === 'multiple' ? `可多选 · 已选 ${selected.length} 项` : '选一个最准确的答案'}</View>
        ) : (
          <>
            <View className={`feedback-banner ${correct ? '' : 'wrong'}`}><Text>{correct ? '✓ 答对啦' : '× 需要订正'}</Text><Text>{correct ? '+10 XP' : '本题 0 XP'}</Text></View>
            <View className='explanation'><View className='explanation-title'>{correct ? '为什么这样选？' : '到底差在哪？'}</View><View className='explanation-copy'>{question.explanation}</View></View>
          </>
        )}

        <View className='quiz-actions'>
          <Button className='ghost-btn' disabled={currentIndex === 0} onClick={goPrevious}>上一题</Button>
          <Button className='primary-btn' disabled={!selected.length} onClick={submitOrContinue}>{submitted ? (currentIndex === quiz.questions.length - 1 ? '完成本关 →' : '继续 →') : '选好了 →'}</Button>
        </View>
      </View>
    </View>
  )
}

