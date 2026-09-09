import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const frontendRoot = new URL('..', import.meta.url).pathname.replace(/^\/(?:([A-Za-z]:))/, '$1')
const read = (path) => readFileSync(join(frontendRoot, path), 'utf8')

test('前端通过任务接口异步生成并固定每 8 秒轮询', () => {
  const api = read('src/services/api.ts')
  const index = read('src/pages/index/index.tsx')

  assert.match(api, /createQuizTask/)
  assert.match(api, /getQuizTask/)
  assert.match(api, /\/quiz\/tasks/)
  assert.match(index, /POLL_INTERVAL_MS\s*=\s*8000/)
  assert.match(index, /setTimeout\([^,]+,\s*POLL_INTERVAL_MS\)/s)
  assert.doesNotMatch(index, /generateQuiz\(/)
})

test('任务完成后保存题目，失败时保留原输入并展示错误', () => {
  const index = read('src/pages/index/index.tsx')

  assert.match(index, /task\.status\s*===\s*['"]completed['"]/)
  assert.match(index, /learningStorage\.saveQuiz\(task\.quiz\)/)
  assert.match(index, /task\.status\s*===\s*['"]failed['"]/)
  assert.match(index, /task\.error_message/)
})
