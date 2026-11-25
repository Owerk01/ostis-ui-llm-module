import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const panel = resolve(here, '../..')

function localImports(path: string): string[] {
  const source = readFileSync(path, 'utf8')
  return [...source.matchAll(/from ['"](\.[^'"]+)['"]/g)].map((match) => match[1])
}

/** Все локальные модули, досягаемые из публичного entry транспорта. */
function reachable(): string[] {
  const seen = new Set<string>()
  const queue = [resolve(here, 'index.ts')]
  while (queue.length > 0) {
    const path = queue.shift()!
    if (seen.has(path)) continue
    seen.add(path)
    for (const specifier of localImports(path)) {
      const withExt = specifier.endsWith('.ts') ? specifier : `${specifier}.ts`
      const next = resolve(dirname(path), withExt)
      if (existsSync(next)) queue.push(next)
    }
  }
  return [...seen]
}

test('публичный entry транспорта не тянет React, CSS и AssistantPanel', () => {
  const files = reachable()
  assert.ok(files.length > 5)
  for (const path of files) {
    const source = readFileSync(path, 'utf8')
    assert.doesNotMatch(source, /from ['"]react/, path)
    assert.doesNotMatch(source, /\.module\.css/, path)
    assert.doesNotMatch(source, /import[^;]*AssistantPanel/, path)
  }
})

test('package.json объявляет отдельную сборку транспорта', () => {
  const pkg = JSON.parse(readFileSync(resolve(panel, 'package.json'), 'utf8'))
  assert.match(pkg.scripts['build:transport'], /vite build --mode transport/)
  assert.ok(pkg.exports['./transport'])
  const peers = Object.keys(pkg.peerDependencies)
  assert.deepEqual(peers.sort(), ['react', 'react-dom', 'ts-sc-client'])
})

test('собранный пакет не содержит React в зависимостях', (t) => {
  const path = resolve(panel, 'dist-transport/package.json')
  if (!existsSync(path)) {
    t.skip('пакет ещё не собран: npm run build:transport')
    return
  }
  const pkg = JSON.parse(readFileSync(path, 'utf8'))
  assert.equal(pkg.dependencies, undefined)
  assert.deepEqual(Object.keys(pkg.peerDependencies ?? {}), ['ts-sc-client'])
})
