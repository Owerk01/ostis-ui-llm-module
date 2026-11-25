import assert from 'node:assert/strict'
import test from 'node:test'

import { parseServiceState, serviceAlive, SERVICE_LEASE_TTL_S } from './serviceHealth.ts'

const SNAPSHOT = JSON.stringify({
  instance_id: 'host:1:abc',
  state: 'ready',
  heartbeat_at: '2026-11-25T12:00:00Z',
  model: 'qwen3.5:4b',
  backend: 'ollama',
  prompt_version: 'v4',
  pack_version: '2026-11-18T00:00:00Z',
  knowledge_source: 'kb',
  contract_version: '0.1.0',
  queue_capacity: 16,
  queue_size: 0,
  active_requests: 0,
  pid: 1,
  host: 'host',
})

const NOW = Date.parse('2026-11-25T12:00:05Z')

test('parseServiceState: поля узла состояния доступны до первого ответа', () => {
  const snapshot = parseServiceState(SNAPSHOT)
  assert.ok(snapshot)
  assert.equal(snapshot.state, 'ready')
  assert.equal(snapshot.model, 'qwen3.5:4b')
  assert.equal(snapshot.packVersion, '2026-11-18T00:00:00Z')
  assert.equal(snapshot.promptVersion, 'v4')
  assert.equal(snapshot.knowledgeSource, 'kb')
  assert.equal(snapshot.contractVersion, '0.1.0')
  assert.equal(snapshot.queueSize, 0)
})

test('parseServiceState: пустой или битый JSON — null', () => {
  assert.equal(parseServiceState(null), null)
  assert.equal(parseServiceState('not-json'), null)
  assert.equal(parseServiceState('[]'), null)
})

test('serviceAlive: свежий heartbeat и состояние ready', () => {
  const snapshot = parseServiceState(SNAPSHOT)
  assert.ok(snapshot)
  assert.equal(serviceAlive(snapshot, NOW), true)
  assert.equal(serviceAlive(snapshot, Date.parse('2026-11-25T12:00:00Z') + SERVICE_LEASE_TTL_S * 1000), true)
})

test('serviceAlive: протухший heartbeat, stopped и будущее время', () => {
  const snapshot = parseServiceState(SNAPSHOT)
  assert.ok(snapshot)
  assert.equal(serviceAlive(snapshot, NOW + (SERVICE_LEASE_TTL_S + 1) * 1000), false)
  assert.equal(serviceAlive(snapshot, NOW - 6000), false)
  assert.equal(serviceAlive({ ...snapshot, state: 'stopped' }, NOW), false)
  assert.equal(serviceAlive({ ...snapshot, heartbeatAt: null }, NOW), false)
})
