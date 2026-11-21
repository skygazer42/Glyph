import request from './request'

// DSL相关API（匹配后端实际API）
export const dslApi = {
  // 从文本生成DSL
  generateFromText(text, metadata = {}) {
    return request.post('/dsl/generate', { text, ...metadata }, { silentError: true })
  },

  // 保存DSL到文件
  saveDSL({ rule_id, yaml_content, filename }) {
    return request.post('/dsl/save', {
      rule_id,
      yaml_content,
      filename
    }, { silentError: true })
  },

  // 获取DSL列表
  listDSL(params = {}) {
    return request.get('/dsl/list', { params, silentError: true })
  },

  // 测试DSL规则
  testDSL(ruleId, inputs) {
    return request.post('/dsl/test', { rule_id: ruleId, inputs }, { silentError: true })
  },

  previewDSL(yamlContent, inputs) {
    return request.post('/dsl/preview', { yaml_content: yamlContent, inputs }, { silentError: true })
  },

  // 获取DSL详情
  getDSL(ruleId) {
    return request.get(`/dsl/${ruleId}`, { silentError: true })
  }
}

// 数据库连接相关 API
export const dbApi = {
  listConnections() {
    return request.get('/db/connections')
  },

  getConnection(id) {
    return request.get(`/db/connections/${id}`)
  }
}

// 知识库相关API（匹配后端实际API）
export const knowledgeApi = {
  // 上传单个文档
  uploadDocument(formData, options = {}) {
    return request.post('/knowledge/upload', formData, {
      silentError: true,
      ...options,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 解析文档为 Markdown（调用 MinerU 等解析器）
  parseDocument(docId, options = {}) {
    const { signal, ...payload } = options
    return request.post('/knowledge/parse', { doc_id: docId, ...payload }, { signal, silentError: true })
  },

  // 嵌入文档到向量库
  embedDocument(docId, options = {}) {
    const { signal, ...payload } = options
    return request.post('/knowledge/embed', { doc_id: docId, ...payload }, { signal, silentError: true })
  },

  // 搜索知识库
  search(query, options = {}) {
    const { topK = 10, threshold = 0.7, signal } = options
    return request.post('/knowledge/search', {
      query,
      top_k: topK,
      threshold
    }, { signal, silentError: true })
  },

  // 获取文档列表
  listDocuments(params = {}, options = {}) {
    return request.get('/knowledge/documents', { params, silentError: true, ...options })
  },

  getCapabilities(options = {}) {
    return request.get('/knowledge/capabilities', { silentError: true, ...options })
  },

  getDocumentWorkspace(docId, options = {}) {
    return request.get(`/knowledge/documents/${encodeURIComponent(docId)}/workspace`, {
      silentError: true,
      ...options
    })
  },

  previewChunks(docId, payload, options = {}) {
    return request.post(`/knowledge/documents/${encodeURIComponent(docId)}/chunks/preview`, payload, {
      silentError: true,
      ...options
    })
  },

  saveProcessingConfig(docId, payload) {
    return request.put(`/knowledge/documents/${encodeURIComponent(docId)}/processing-config`, payload, {
      silentError: true
    })
  },

  // 删除单个文档
  deleteDocument(docId) {
    return request.delete(`/knowledge/documents/${docId}`)
  },

  // 获取统计信息
  getStats() {
    return request.get('/knowledge/stats')
  }
}

// 系统API
export const systemApi = {
  // 获取系统状态
  getStatus() {
    return request.get('/system/status')
  },

  // 获取配置
  getConfig() {
    return request.get('/system/config')
  },

  // 更新配置
  updateConfig(config) {
    return request.put('/system/config', config)
  }
}

// Agent相关API（匹配后端实际API）
export const agentApi = {
  // 发送消息（非流式）- 支持会话、数据库连接以及用户ID
  chat(
    message,
    sessionId = null,
    connectionId = null,
    userId = null,
    attachments = null,
    options = {}
  ) {
    const { staffRequest = false, ...chatOptions } = options
    const payload = {
      message,
      session_id: sessionId,
      connection_id: connectionId,
      ...chatOptions
    }

    if (userId !== null && userId.length > 0) {
      payload.user_id = userId
    }

    if (attachments !== null && attachments.length > 0) {
      payload.attachments = attachments
    }

    return request.post('/agent/chat', payload, {
      staffRequest,
      headers: { 'X-Client-Audience': staffRequest ? 'staff' : 'public' }
    })
  },

  // 发送消息（流式）- 通过POST发送，使用SSE接收
  // 注意：不使用EventSource，而是在组件中直接fetch
  chatStreamUrl: '/agent/chat/stream',
  aguiUrl: '/agent/ag-ui',

  // 获取会话信息
  getSession(sessionId) {
    return request.get(`/agent/sessions/${encodeURIComponent(sessionId)}`, { staffRequest: true })
  },

  // 获取所有会话列表
  listSessions() {
    return request.get('/agent/sessions', { staffRequest: true })
  },

  // 删除会话
  deleteSession(sessionId) {
    return request.delete(`/agent/sessions/${encodeURIComponent(sessionId)}`, { staffRequest: true })
  },

  // 获取会话消息历史
  getSessionMessages(sessionId, limit = null) {
    const params = limit !== null && limit !== 0 ? { limit } : {}
    return request.get(`/agent/sessions/${encodeURIComponent(sessionId)}/messages`, { params, staffRequest: true })
  }
}

// 知识图谱相关API
export const graphApi = {
  getSubgraph(params = {}, options = {}) {
    return request.get('/knowledge-graph/subgraph', { params, silentError: true, ...options })
  },

  searchEntities(query, options = {}) {
    return request.get('/knowledge-graph/search', { params: { q: query, limit: 12 }, silentError: true, ...options })
  },
  // 获取知识图谱数据
  getGraphData() {
    return request.get('/knowledge-graph/graph')
  },

  // 获取图谱统计信息
  getGraphStats() {
    return request.get('/knowledge-graph/graph/stats')
  }
}

// 导出统一的 getGraphData 函数供组件使用
export const getGraphData = graphApi.getGraphData
