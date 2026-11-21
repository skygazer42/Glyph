import assert from 'node:assert/strict'
import test from 'node:test'
import { applyAguiEvent, createAguiRunState, readAguiStream } from '../src/utils/aguiStream.js'

const started = { type: 'RUN_STARTED', runId: 'run-1', threadId: 'thread-1' }
const finished = { type: 'RUN_FINISHED', runId: 'run-1', threadId: 'thread-1' }
const textStart = { type: 'TEXT_MESSAGE_START', messageId: 'answer-1', role: 'assistant' }
const textEnd = { type: 'TEXT_MESSAGE_END', messageId: 'answer-1' }
const frame = event => `data: ${JSON.stringify(event)}\n\n`
const encode = source => new TextEncoder().encode(source)

function streamOf(chunks) {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk)
      controller.close()
    }
  })
}

test('run state starts without fabricated tool progress or content', () => {
  const state = createAguiRunState('run-1')
  assert.equal(state.runId, 'run-1')
  assert.equal(state.status, 'connecting')
  assert.equal(state.phase, '正在连接咨询服务')
  assert.equal(state.content, '')
  assert.equal(state.finished, false)
  assert.deepEqual(state.steps, [])
  assert.deepEqual(state.tools, [])
})

test('text deltas are replaced by the authoritative final answer without duplication', () => {
  const state = createAguiRunState('run-1')
  const sources = [{ title: '住房政策', url: 'https://example.gov.cn/policy' }]
  for (const event of [
    started,
    { type: 'CUSTOM', name: 'glyph.session', value: { session_id: 'signed-session' } },
    { type: 'CUSTOM', name: 'glyph.sources', value: { sources } },
    textStart,
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'answer-1', delta: '可提取' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'answer-1', delta: '公积金。' },
    textEnd,
    { type: 'CUSTOM', name: 'glyph.answer', value: { content: '可提取公积金。[资料1]', metadata: { route: 'knowledge' } } },
    finished
  ]) applyAguiEvent(state, event)
  assert.equal(state.content, '可提取公积金。[资料1]')
  assert.equal(state.sessionId, 'signed-session')
  assert.deepEqual(state.sources, sources)
  assert.deepEqual(state.metadata.sources, sources)
  assert.equal(state.metadata.route, 'knowledge')
  assert.equal(state.status, 'complete')
  assert.equal(state.finished, true)
})

test('an explicit empty final sources list replaces earlier provisional sources', () => {
  const state = createAguiRunState('run-1')
  applyAguiEvent(state, started)
  applyAguiEvent(state, { type: 'CUSTOM', name: 'glyph.sources', value: { sources: [{ title: 'early' }] } })
  applyAguiEvent(state, { type: 'CUSTOM', name: 'glyph.answer', value: { content: '需进一步核对', metadata: { sources: [] } } })
  assert.deepEqual(state.sources, [])
  assert.deepEqual(state.metadata.sources, [])
})

test('real step and tool events update status without leaking tool payload into the answer', () => {
  const state = createAguiRunState('run-1')
  for (const event of [
    started,
    { type: 'STEP_STARTED', stepName: '检索政策' },
    { type: 'TOOL_CALL_START', toolCallId: 'tool-1', toolCallName: 'knowledge_tool' },
    { type: 'TOOL_CALL_ARGS', toolCallId: 'tool-1', delta: '{"query":"住房"}' },
    { type: 'TOOL_CALL_END', toolCallId: 'tool-1' },
    { type: 'TOOL_CALL_RESULT', toolCallId: 'tool-1', messageId: 'result-1', content: 'private diagnostic text', role: 'tool' },
    { type: 'STEP_FINISHED', stepName: '检索政策' }
  ]) applyAguiEvent(state, event)
  assert.equal(state.steps.length, 1)
  assert.equal(state.steps[0].status, 'complete')
  assert.equal(state.tools.length, 1)
  assert.equal(state.tools[0].status, 'complete')
  assert.equal(state.tools[0].args, '{"query":"住房"}')
  assert.equal(state.content, '')
  assert.match(state.phase, /政策/)
  assert.ok(!state.phase.includes('knowledge_tool'))
})

test('unknown tool and step names cannot read object prototype properties', () => {
  const state = createAguiRunState('run-1')
  applyAguiEvent(state, started)
  applyAguiEvent(state, { type: 'STEP_STARTED', stepName: 'constructor' })
  assert.equal(state.phase, '正在处理咨询')
  applyAguiEvent(state, { type: 'TOOL_CALL_START', toolCallId: 'tool-1', toolCallName: '__proto__' })
  assert.equal(state.phase, '正在处理咨询')
})

for (const status of ['error', 'cancelled']) {
  test(`finished steps and tools preserve backend ${status} status`, () => {
    const state = createAguiRunState('run-1')
    for (const event of [
      started,
      { type: 'STEP_STARTED', stepName: '检索政策' },
      { type: 'TOOL_CALL_START', toolCallId: 'tool-1', toolCallName: 'knowledge_tool' },
      { type: 'STEP_FINISHED', stepName: '检索政策', metadata: { status } },
      { type: 'TOOL_CALL_END', toolCallId: 'tool-1', metadata: { status } }
    ]) applyAguiEvent(state, event)
    assert.equal(state.steps[0].status, status)
    assert.equal(state.tools[0].status, status)
    applyAguiEvent(state, { type: 'TOOL_CALL_RESULT', toolCallId: 'tool-1', messageId: 'result-1', content: '工具暂未完成', role: 'tool' })
    assert.equal(state.tools[0].status, status)
    assert.equal(state.content, '')
  })
}

test('explicit completed metadata closes steps and tools before their safe result arrives', () => {
  const state = createAguiRunState('run-1')
  for (const event of [
    started,
    { type: 'STEP_STARTED', stepName: '检索政策' },
    { type: 'TOOL_CALL_START', toolCallId: 'tool-1', toolCallName: 'knowledge_tool' },
    { type: 'STEP_FINISHED', stepName: '检索政策', metadata: { status: 'completed' } },
    { type: 'TOOL_CALL_END', toolCallId: 'tool-1', metadata: { status: 'completed' } },
    { type: 'CUSTOM', name: 'glyph.heartbeat', value: {} }
  ]) applyAguiEvent(state, event)
  assert.equal(state.steps[0].status, 'complete')
  assert.equal(state.tools[0].status, 'complete')
  assert.equal(state.finished, false)
  assert.equal(state.content, '')
})

test('unrelated run and message identifiers cannot overwrite this answer', () => {
  const state = createAguiRunState('run-1')
  applyAguiEvent(state, { ...started, runId: 'old-run' })
  assert.equal(state.status, 'connecting')
  applyAguiEvent(state, started)
  applyAguiEvent(state, textStart)
  applyAguiEvent(state, { type: 'TEXT_MESSAGE_CONTENT', messageId: 'old-answer', delta: '旧结果' })
  applyAguiEvent(state, { type: 'TEXT_MESSAGE_CONTENT', messageId: 'answer-1', delta: '当前结果' })
  applyAguiEvent(state, { type: 'CUSTOM', runId: 'old-run', name: 'glyph.answer', value: { content: '旧快照' } })
  applyAguiEvent(state, { ...finished, runId: 'old-run' })
  assert.equal(state.content, '当前结果')
  assert.equal(state.finished, false)
})

test('only assistant text messages become answer content', () => {
  const state = createAguiRunState('run-1')
  for (const event of [
    started,
    { type: 'TEXT_MESSAGE_START', messageId: 'tool-output', role: 'tool' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'tool-output', delta: '工具内部结果' },
    { type: 'TEXT_MESSAGE_END', messageId: 'tool-output' },
    { type: 'REASONING_MESSAGE_CONTENT', messageId: 'reasoning', delta: '推理内容' },
    textStart,
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'answer-1', delta: '政策答复' },
    textEnd,
    finished
  ]) applyAguiEvent(state, event)
  assert.equal(state.content, '政策答复')
})

test('events cannot create content before the run starts or finish an open message', () => {
  const state = createAguiRunState('run-1')
  assert.throws(() => applyAguiEvent(state, textStart), /开始/)
  applyAguiEvent(state, started)
  applyAguiEvent(state, textStart)
  assert.throws(() => applyAguiEvent(state, finished), /正文|结束/)
  assert.equal(state.finished, false)
})

test('run errors remain errors even if later frames claim completion', () => {
  const state = createAguiRunState('run-1')
  applyAguiEvent(state, started)
  applyAguiEvent(state, { type: 'RUN_ERROR', message: '政策检索暂时不可用' })
  applyAguiEvent(state, finished)
  assert.equal(state.status, 'error')
  assert.equal(state.error, '政策检索暂时不可用')
  assert.equal(state.finished, true)
})

test('reader handles byte-split Chinese, CRLF, comment pings and multiline JSON data', async () => {
  const source = ': ping\r\n\r\n' +
    'data: {"type":\r\ndata: "RUN_STARTED","runId":"run-1","threadId":"thread-1"}\r\n\r\n' +
    frame(textStart) +
    frame({ type: 'TEXT_MESSAGE_CONTENT', messageId: 'answer-1', delta: '住房公积金' }) +
    frame(textEnd) + frame(finished)
  const bytes = encode(source)
  const body = streamOf([...bytes].map(byte => Uint8Array.of(byte)))
  const state = createAguiRunState('run-1')
  await readAguiStream(body, event => applyAguiEvent(state, event))
  assert.equal(state.content, '住房公积金')
  assert.equal(state.finished, true)
  assert.equal(body.locked, false)
})

test('RUN_ERROR is a terminal protocol event dispatched to the caller', async () => {
  const body = streamOf([encode(frame(started) + frame({ type: 'RUN_ERROR', message: '暂时不可用' }))])
  const state = createAguiRunState('run-1')
  await readAguiStream(body, event => applyAguiEvent(state, event))
  assert.equal(state.status, 'error')
  assert.equal(body.locked, false)
})

test('EOF without a terminal event reports interruption and releases the reader', async () => {
  const body = streamOf([encode(frame(started) + frame(textStart))])
  await assert.rejects(readAguiStream(body, () => {}), /中断|完成/)
  assert.equal(body.locked, false)
})

test('a wrong-run terminal frame does not hide a truncated current run', async () => {
  const body = streamOf([encode(frame(started) + frame({ ...finished, runId: 'old-run' }))])
  await assert.rejects(readAguiStream(body, () => {}), /中断|完成/)
})

test('invalid JSON and callback failures cancel the stream and release its lock', async () => {
  let cancellations = 0
  const malformed = new ReadableStream({
    start(controller) { controller.enqueue(encode('data: {bad json}\n\n')) },
    cancel() { cancellations++ }
  })
  await assert.rejects(readAguiStream(malformed, () => {}), /事件|JSON/)
  assert.equal(cancellations, 1)
  assert.equal(malformed.locked, false)
  const rejected = new ReadableStream({
    start(controller) { controller.enqueue(encode(frame(started))) },
    cancel() { cancellations++ }
  })
  await assert.rejects(readAguiStream(rejected, () => { throw Error('render failed') }), /render failed/)
  assert.equal(cancellations, 2)
  assert.equal(rejected.locked, false)
})

test('abort interrupts an outstanding read and does not issue another request', async () => {
  let cancellations = 0
  const controller = new AbortController()
  const body = new ReadableStream({
    start(stream) { stream.enqueue(encode(frame(started))) },
    cancel() { cancellations++ }
  })
  const pending = readAguiStream(body, () => { controller.abort() }, { signal: controller.signal })
  await assert.rejects(pending, error => error.name === 'AbortError')
  assert.equal(cancellations, 1)
  assert.equal(body.locked, false)
})
