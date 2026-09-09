import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const frontendRoot = new URL('..', import.meta.url).pathname.replace(/^\/(?:([A-Za-z]:))/, '$1')

const pages = {
  index: 'AI闯关学习',
  preview: '闯关预览',
  quiz: '答题闯关',
  result: '闯关结果',
  report: '学习报告',
  profile: '我的',
  'profile-edit': '编辑资料',
  history: '闯关历史',
  'history-detail': '闯关详情',
  source: '资料原文'
}

function read(relativePath) {
  return readFileSync(join(frontendRoot, relativePath), 'utf8')
}

test('全局启用微信原生导航栏并设置默认标题', () => {
  const appConfig = read('src/app.config.ts')
  assert.doesNotMatch(appConfig, /navigationStyle\s*:\s*['"]custom['"]/)
  assert.match(appConfig, /navigationBarTitleText\s*:\s*['"]AI闯关学习['"]/)
  assert.match(appConfig, /navigationBarBackgroundColor\s*:\s*['"]#fff4c7['"]/)
  assert.match(appConfig, /navigationBarTextStyle\s*:\s*['"]black['"]/)
})

for (const [page, title] of Object.entries(pages)) {
  test(`${page} 页面使用原生导航并配置独立标题`, () => {
    const config = read(`src/pages/${page}/index.config.ts`)
    const component = read(`src/pages/${page}/index.tsx`)
    assert.doesNotMatch(config, /navigationStyle\s*:\s*['"]custom['"]/)
    assert.match(config, new RegExp(`navigationBarTitleText\\s*:\\s*['"]${title}['"]`))
    assert.doesNotMatch(component, /<StatusBar\s*\/>/)
    assert.doesNotMatch(component, /components\/StatusBar/)
  })
}
