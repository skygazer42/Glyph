const toolPhases = {
  knowledge_tool: '正在检索政策',
  graph_tool: '正在查询政策关系',
  rule_tool: '正在核对条件与计算',
  text2sql_tool: '正在查询业务数据',
  workflow_tool: '正在处理材料'
}

const stepPhases = {
  context: '正在准备咨询',
  preparation: '正在准备咨询',
  faq: '正在核对政策问答',
  retrieval: '正在检索政策',
  knowledge: '正在检索政策',
  generation: '正在整理答复',
  answer_generation: '正在整理答复'
}

const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const has = (value, key) => Object.hasOwn(value, key)
const phaseForStep = name => has(stepPhases, name) ? stepPhases[name] : (/\p{Script=Han}/u.test(name) ? name : '正在处理咨询')

export function createAguiRunState(runId) {
  if (typeof runId !== 'string' || !runId) throw new TypeError('缺少咨询运行标识')
  return {
    runId,
    threadId: null,
    sessionId: null,
    content: '',
    metadata: {},
    sources: [],
    status: 'connecting',
    phase: '正在连接咨询服务',
    steps: [],
    tools: [],
    finished: false,
    error: null,
    _started: false,
    _messages: Object.create(null),
    _messageOrder: [],
    _hasSnapshot: false
  }
}

function updateSources(state, sources) {
  if (!Array.isArray(sources)) return
  state.sources = [...sources]
  state.metadata = { ...state.metadata, sources: state.sources }
}

function completionStatus(event, fallback) {
  const status = event.metadata?.status
  if (status === 'error' || status === 'cancelled') return status
  return status === 'completed' ? 'complete' : fallback
}

function applyCustomEvent(state, event) {
  const value = event.value
  if (!isRecord(value)) return
  if (event.name === 'glyph.session') {
    if (typeof value.session_id === 'string' && value.session_id) state.sessionId = value.session_id
  } else if (event.name === 'glyph.sources') {
    updateSources(state, value.sources)
  } else if (event.name === 'glyph.answer') {
    if (typeof value.content === 'string') {
      state.content = value.content
      state._hasSnapshot = true
    }
    if (isRecord(value.metadata)) {
      state.metadata = { ...state.metadata, ...value.metadata }
      if (has(value.metadata, 'sources')) updateSources(state, value.metadata.sources)
    }
    if (has(value, 'sources')) updateSources(state, value.sources)
    if (typeof value.session_id === 'string' && value.session_id) state.sessionId = value.session_id
  }
}

/** Apply one event to this request's state; unrelated run/message IDs cannot replace its answer. */
export function applyAguiEvent(state, event) {
  if (!isRecord(event) || typeof event.type !== 'string') throw new TypeError('咨询事件格式无效')
  if (event.runId !== undefined && event.runId !== state.runId) return state
  if (event.threadId !== undefined && state.threadId !== null && event.threadId !== state.threadId) return state
  if (state.finished) return state

  if (event.type === 'RUN_STARTED') {
    if (state._started) throw new Error('咨询运行重复开始')
    if (typeof event.threadId !== 'string' || !event.threadId) throw new Error('咨询事件缺少会话标识')
    state.threadId = event.threadId
    state._started = true
    state.status = 'running'
    state.phase = '正在处理咨询'
    return state
  }
  if (!state._started) throw new Error('咨询运行尚未开始')

  if (event.type === 'RUN_FINISHED') {
    if (Object.values(state._messages).some(message => message.open)) throw new Error('答复正文尚未结束')
    state.status = 'complete'
    state.phase = '答复完成'
    state.finished = true
  } else if (event.type === 'RUN_ERROR') {
    state.status = 'error'
    state.phase = '答复未完成'
    state.error = typeof event.message === 'string' && event.message ? event.message : '咨询暂时不可用，请稍后重试'
    state.finished = true
  } else if (event.type === 'STEP_STARTED') {
    if (typeof event.stepName !== 'string' || !event.stepName) throw new Error('处理阶段缺少名称')
    state.steps.push({ name: event.stepName, status: 'running' })
    state.phase = phaseForStep(event.stepName)
  } else if (event.type === 'STEP_FINISHED') {
    const step = [...state.steps].reverse().find(item => item.name === event.stepName && item.status === 'running')
    if (step) step.status = completionStatus(event, 'complete')
  } else if (event.type === 'TOOL_CALL_START') {
    if (typeof event.toolCallId !== 'string' || !event.toolCallId) throw new Error('工具事件缺少调用标识')
    if (!state.tools.some(tool => tool.id === event.toolCallId)) {
      state.tools.push({ id: event.toolCallId, name: event.toolCallName, status: 'running', args: '' })
    }
    state.phase = has(toolPhases, event.toolCallName) ? toolPhases[event.toolCallName] : '正在处理咨询'
  } else if (event.type === 'TOOL_CALL_ARGS') {
    const tool = state.tools.find(item => item.id === event.toolCallId)
    if (tool && typeof event.delta === 'string') tool.args += event.delta
  } else if (event.type === 'TOOL_CALL_END' || event.type === 'TOOL_CALL_RESULT') {
    const tool = state.tools.find(item => item.id === event.toolCallId)
    if (tool && tool.status !== 'error' && tool.status !== 'cancelled') {
      tool.status = completionStatus(event, event.type === 'TOOL_CALL_RESULT' ? 'complete' : 'awaiting_result')
    }
  } else if (event.type === 'TEXT_MESSAGE_START') {
    if (typeof event.messageId !== 'string' || !event.messageId) throw new Error('答复事件缺少消息标识')
    if (has(state._messages, event.messageId)) throw new Error('答复消息重复开始')
    const role = event.role ?? 'assistant'
    state._messages[event.messageId] = { role, content: '', open: true }
    state._messageOrder.push(event.messageId)
    if (role === 'assistant') state.phase = '正在生成答复'
  } else if (event.type === 'TEXT_MESSAGE_CONTENT') {
    if (!state._messageOrder.length) throw new Error('答复正文尚未开始')
    const message = state._messages[event.messageId]
    if (!message?.open || message.role !== 'assistant' || state._hasSnapshot) return state
    if (typeof event.delta !== 'string') throw new Error('答复片段格式无效')
    message.content += event.delta
    state.content = state._messageOrder
      .map(id => state._messages[id])
      .filter(item => item.role === 'assistant')
      .map(item => item.content)
      .join('\n\n')
  } else if (event.type === 'TEXT_MESSAGE_END') {
    const message = state._messages[event.messageId]
    if (message) message.open = false
  } else if (event.type === 'CUSTOM') {
    applyCustomEvent(state, event)
  }
  return state
}

function abortError() {
  return new DOMException('咨询已停止', 'AbortError')
}

/** Read official AG-UI SSE data frames without replaying the request on failure. */
export async function readAguiStream(body, onEvent, { signal } = {}) {
  if (signal?.aborted) throw abortError()
  if (!body || typeof body.getReader !== 'function') throw new Error('浏览器不支持流式响应')
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let buffer = ''
  let runId = null
  let threadId = null
  let terminal = false
  const stopReading = () => { reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', stopReading, { once: true })

  const processFrame = source => {
    const data = source.split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (!data) return
    let event
    try {
      event = JSON.parse(data)
    } catch {
      throw new Error('咨询事件 JSON 格式无效')
    }
    if (!isRecord(event) || typeof event.type !== 'string') throw new Error('咨询事件格式无效')
    if (runId !== null && event.runId !== undefined && event.runId !== runId) return
    if (threadId !== null && event.threadId !== undefined && event.threadId !== threadId) return
    if (event.type === 'RUN_STARTED') {
      if (runId !== null) throw new Error('咨询运行重复开始')
      if (typeof event.runId !== 'string' || typeof event.threadId !== 'string') throw new Error('咨询运行标识无效')
      runId = event.runId
      threadId = event.threadId
    } else if (runId === null) {
      throw new Error('咨询运行尚未开始')
    }
    onEvent(event)
    terminal = event.type === 'RUN_FINISHED' || event.type === 'RUN_ERROR'
    if (signal?.aborted) throw abortError()
  }

  try {
    while (!terminal) {
      const chunk = await reader.read()
      if (signal?.aborted) throw abortError()
      if (chunk.done) {
        buffer += decoder.decode()
        break
      }
      buffer += decoder.decode(chunk.value, { stream: true })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        processFrame(frame)
        if (terminal) break
      }
    }
    if (!terminal) throw new Error('咨询事件流意外中断，请重试')
  } finally {
    signal?.removeEventListener('abort', stopReading)
    try {
      await reader.cancel()
    } catch {
      // Preserve the processing or transport error when cleanup itself fails.
    }
    reader.releaseLock()
  }
}
