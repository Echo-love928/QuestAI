import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import test from 'node:test'

const pagesRoot = join(process.cwd(), 'src', 'pages')

function collectTsxFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectTsxFiles(path)
    return entry.name.endsWith('.tsx') ? [path] : []
  })
}

test('page text nodes do not render escaped newline tokens', () => {
  const visibleEscape = /<Text\b[^>]*>\s*\\n\s*<\/Text>/
  const affectedFiles = collectTsxFiles(pagesRoot)
    .filter((path) => visibleEscape.test(readFileSync(path, 'utf8')))
    .map((path) => relative(process.cwd(), path))

  assert.deepEqual(affectedFiles, [])
})
