import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('knowledge pages use native navigation and are registered', () => {
  const app = read('src/app.config.ts')
  for (const page of ['knowledge/index', 'knowledge-create/index', 'knowledge-detail/index', 'knowledge-upload/index']) {
    assert.match(app, new RegExp(`pages/${page}`))
  }
  for (const page of ['knowledge', 'knowledge-create', 'knowledge-detail', 'knowledge-upload']) {
    const config = read(`src/pages/${page}/index.config.ts`)
    assert.match(config, /navigationBarTitleText/)
    assert.doesNotMatch(config, /navigationStyle\s*:\s*['"]custom/)
  }
})

test('document upload uses official Taro file APIs and enforces 10MB formats', () => {
  const page = read('src/pages/knowledge-upload/index.tsx')
  const api = read('src/services/api.ts')
  assert.match(page, /Taro\.chooseMessageFile/)
  assert.match(page, /10 \* 1024 \* 1024/)
  assert.match(page, /'pdf', 'doc', 'docx', 'md'/)
  assert.match(api, /Taro\.uploadFile/)
  assert.match(api, /name: 'file'/)
  assert.match(api, /Authorization/)
})

test('private and mixed generation send selected knowledge bases without changing legacy call shape', () => {
  const page = read('src/pages/index/index.tsx')
  const api = read('src/services/api.ts')
  assert.match(page, /sourceScope === 'private'/)
  assert.match(page, /selectedKnowledgeBaseIds/)
  assert.match(page, /POLL_INTERVAL_MS = 8000/)
  assert.match(api, /source_scope: source\.scope/)
  assert.match(api, /knowledge_base_ids: source\.knowledgeBaseIds/)
  assert.match(api, /source\?: \{ scope: SourceScope/)
})

test('private citations show safe document locations and never offer URL actions', () => {
  const panel = read('src/components/SourcePanel.tsx')
  assert.match(panel, /source\.source_type === 'private_document'/)
  assert.match(panel, /source\.location/)
  assert.match(panel, /source\.source_type !== 'private_document'/)
})

test('profile keeps existing records and adds the private cabinet entry', () => {
  const profile = read('src/pages/profile/index.tsx')
  assert.match(profile, /我的资料库/)
  assert.match(profile, /最近闯关/)
  assert.match(profile, /pages\/knowledge\/index/)
})
