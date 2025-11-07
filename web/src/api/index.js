import request from './request'

// DSL相关API - 优化版本
export const dslApi = {
  // 从文本生成DSL（支持元数据）
  generateFromText(text, metadata = {}) {
    return request.post('/dsl/generate', { text, metadata })
  },

  // 从文件生成DSL
  generateFromFile(formData) {
    return request.post('/dsl/generate-from-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 批量生成DSL
  batchGenerate(documents) {
    return request.post('/dsl/batch-generate', { documents })
  },

  // 保存DSL
  saveDSL(dslData) {
    return request.post('/dsl/save', dslData)
  },

  // 获取DSL列表（支持分页和过滤）
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
  },

  // 更新DSL
  updateDSL(ruleId, dslData) {
    return request.put(`/dsl/${ruleId}`, dslData)
  },

  // 删除DSL
  deleteDSL(ruleId) {
    return request.delete(`/dsl/${ruleId}`)
  },

  // 导出DSL
  exportDSL(ruleIds) {
    return request.post('/dsl/export', { rule_ids: ruleIds }, {
      responseType: 'blob'
    })
  },

  // 导入DSL
  importDSL(formData) {
    return request.post('/dsl/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

// 知识库相关API - 优化版本
export const knowledgeApi = {
  // 上传文档（支持批量）
  uploadDocument(formData) {
    return request.post('/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 嵌入文档到向量库（支持批量）
  embedDocument(docIds) {
    const payload = Array.isArray(docIds) ? { doc_ids: docIds } : { doc_id: docIds }
    return request.post('/knowledge/embed', payload)
  },

  // 搜索知识库（增强选项）
  search(query, options = {}) {
    const { topK = 10, filters = {}, rerank = false } = options
    return request.post('/knowledge/search', {
      query,
      top_k: topK,
      filters,
      rerank
    })
  },

  // 混合搜索（BM25 + 向量）
  hybridSearch(query, options = {}) {
    return request.post('/knowledge/hybrid-search', { query, ...options })
  },

  // 获取文档列表（支持分页）
  listDocuments(params = {}) {
    return request.get('/knowledge/documents', { params })
  },

  // 删除文档（支持批量）
  deleteDocument(docIds) {
    if (Array.isArray(docIds)) {
      return request.delete('/knowledge/documents/batch', { data: { doc_ids: docIds } })
    }
    return request.delete(`/knowledge/documents/${docIds}`)
  },

  // 获取文档详情
  getDocument(docId) {
    return request.get(`/knowledge/documents/${docId}`)
  },

  // 重建索引
  rebuildIndex() {
    return request.post('/knowledge/rebuild-index')
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
