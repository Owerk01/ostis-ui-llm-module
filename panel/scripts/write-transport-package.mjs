/**
 * Финализация отдельного пакета транспорта: версия берётся из корневого VERSION.
 * У пакета нет зависимостей от React; ts-sc-client остаётся peerDependency.
 */

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '../..')
const outDir = resolve(here, '../dist-transport')
const version = readFileSync(resolve(root, 'VERSION'), 'utf8').trim()

const pkg = {
  name: 'ostis-ui-assistant-dialog-transport',
  version,
  private: false,
  type: 'module',
  description: 'Диалоговый транспорт ассистента: sc-memory и direct-http, без UI',
  main: './index.js',
  module: './index.js',
  types: './index.d.ts',
  exports: {
    '.': {
      types: './index.d.ts',
      import: './index.js',
    },
  },
  files: ['index.js', '*.d.ts'],
  sideEffects: false,
  peerDependencies: {
    'ts-sc-client': '^0.5.0',
  },
}

mkdirSync(outDir, { recursive: true })
writeFileSync(
  resolve(outDir, 'package.json'),
  `${JSON.stringify(pkg, null, 2)}\n`,
  'utf8',
)

// Исходники используют .ts для node --experimental-strip-types; в .d.ts эти
// суффиксы нужно убрать, чтобы потребитель с NodeNext находил *.d.ts.
for (const name of readdirSync(outDir)) {
  if (!name.endsWith('.d.ts')) continue
  const path = join(outDir, name)
  const text = readFileSync(path, 'utf8')
  writeFileSync(path, text.replaceAll(".ts'", "'"), 'utf8')
}

console.log(`dialog-transport ${version}: package.json записан в dist-transport/`)
