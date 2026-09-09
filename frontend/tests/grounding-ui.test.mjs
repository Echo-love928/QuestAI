import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const frontendRoot = new URL('..', import.meta.url).pathname.replace(/^\/(?:([A-Za-z]:))/, '$1')
const read = (path) => readFileSync(join(frontendRoot, path), 'utf8')

test('题库契约兼容文本、URL、依据模式、来源和逐题引用', () => {
  const types = read('src/types/api.ts')
  assert.match(types, /InputSourceType\s*=\s*['"]text['"]\s*\|\s*['"]url['"]/)
  assert.match(types, /GroundingMode\s*=.*user_content.*web_search.*url_extract.*mixed/s)
  assert.match(types, /interface GroundingSource/)
  assert.match(types, /source_ids\??:\s*string\[\]/)
  assert.match(types, /sources\??:\s*GroundingSource\[\]/)
})

test('旧缓存通过规范化函数补齐可选依据字段', () => {
  const storage = read('src/utils/storage.ts')
  assert.match(storage, /normalizeQuiz/)
  assert.match(storage, /grounding_mode/)
  assert.match(storage, /sources/)
})

test('URL 输入校验、来源类型请求体及可取消请求均已实现', () => {
  const index = read('src/pages/index/index.tsx')
  const api = read('src/services/api.ts')
  assert.match(index, /isValidPublicUrl/)
  assert.match(index, /sourceType/)
  assert.match(index, /useUnload/)
  assert.match(api, /source_type:\s*sourceType/)
  assert.match(api, /abort:\s*\(\)/)
  assert.match(api, /requestTask\.abort\(\)/)
})

test('生成阶段和分类错误操作保留原输入', () => {
  const index = read('src/pages/index/index.tsx')
  for (const label of ['搜索资料', '提取网页', '核对依据', '重新获取资料', '检查网址', '返回修改内容']) {
    assert.match(index, new RegExp(label))
  }
  assert.match(index, /RESEARCH_EVIDENCE_INSUFFICIENT/)
  assert.match(index, /RESEARCH_AMBIGUOUS/)
  assert.match(index, /RESEARCH_URL_/)
})

test('预览、答题讲解和历史详情复用来源组件', () => {
  const component = read('src/components/SourcePanel.tsx')
  assert.match(component, /https:\/\//)
  assert.match(component, /setClipboardData/)
  assert.match(component, /依据你提供的内容生成/)
  assert.match(component, /历史记录未保存来源/)
  for (const page of ['preview', 'quiz', 'history-detail']) {
    assert.match(read(`src/pages/${page}/index.tsx`), /SourcePanel/)
  }
})
