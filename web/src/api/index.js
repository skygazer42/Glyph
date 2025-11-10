import request from './request'

// DSL相关API（匹配后端实际API）
export const dslApi = {
  // 从文本生成DSL
  generateFromText(text, metadata = {}) {
    return request.post('/dsl/generate', { text, ...metadata })
  },

  // 保存DSL到文件
  saveDSL(data) {
    return request.post('/dsl/save', {
      rule_id: data.rule_id,
      yaml_content: data.yaml_content,
      filename: data.filename
    })
  },

  // 获取DSL列表
  listDSL(params = {}) {
    return request.get('/dsl/list', { params })
  },

  // 测试DSL规则
  testDSL(ruleId, inputs) {
    return request.post('/dsl/test', { rule_id: ruleId, inputs })
  },

  // 获取DSL详情
  getDSL(ruleId) {
    return request.get(`/dsl/${ruleId}`)
  }
}

// 知识库相关API（匹配后端实际API）
export const knowledgeApi = {
  // 上传单个文档
  uploadDocument(formData) {
    return request.post('/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 嵌入文档到向量库
  embedDocument(docId) {
    return request.post('/knowledge/embed', { doc_id: docId })
  },

  // 搜索知识库
  search(query, options = {}) {
    const { topK = 10, threshold = 0.7 } = options
    return request.post('/knowledge/search', {
      query,
      top_k: topK,
      threshold
    })
  },

  // 获取文档列表
  listDocuments(params = {}) {
    return request.get('/knowledge/documents', { params })
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
  // 发送消息（非流式）- 支持会话和数据库连接
  chat(message, sessionId = null, connectionId = null) {
    return request.post('/agent/chat', {
      message,
      session_id: sessionId,
      connection_id: connectionId
    })
  },

  // 发送消息（流式）- 通过POST发送，使用SSE接收
  // 注意：不使用EventSource，而是在组件中直接fetch
  chatStreamUrl: '/agent/chat/stream',

  // 获取会话信息
  getSession(sessionId) {
    return request.get(`/agent/sessions/${sessionId}`)
  },

  // 获取所有会话列表
  listSessions() {
    return request.get('/agent/sessions')
  },

  // 删除会话
  deleteSession(sessionId) {
    return request.delete(`/agent/sessions/${sessionId}`)
  },

  // 获取会话消息历史
  getSessionMessages(sessionId, limit = null) {
    const params = limit ? { limit } : {}
    return request.get(`/agent/sessions/${sessionId}/messages`, { params })
  }
}
