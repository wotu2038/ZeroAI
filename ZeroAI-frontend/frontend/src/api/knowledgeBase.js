import api from './index'

/**
 * 获取知识库列表
 */
export const getKnowledgeBases = (params = {}) => {
  return api.get('/knowledge-bases', { params })
}

/**
 * 获取知识库详情
 */
export const getKnowledgeBase = (kbId) => {
  return api.get(`/knowledge-bases/${kbId}`)
}

/**
 * 创建知识库
 */
export const createKnowledgeBase = (data) => {
  return api.post('/knowledge-bases', data)
}

/**
 * 更新知识库
 */
export const updateKnowledgeBase = (kbId, data) => {
  return api.put(`/knowledge-bases/${kbId}`, data)
}

/**
 * 删除知识库
 */
export const deleteKnowledgeBase = (kbId) => {
  return api.delete(`/knowledge-bases/${kbId}`)
}

/**
 * 获取知识库成员列表
 */
export const getMembers = (kbId) => {
  return api.get(`/knowledge-bases/${kbId}/members`)
}

/**
 * 添加成员
 */
export const addMember = (kbId, data) => {
  return api.post(`/knowledge-bases/${kbId}/members`, data)
}

/**
 * 移除成员
 */
export const removeMember = (kbId, memberName) => {
  return api.delete(`/knowledge-bases/${kbId}/members/${memberName}`)
}

/**
 * 加入知识库
 */
export const joinKnowledgeBase = (kbId) => {
  return api.post(`/knowledge-bases/${kbId}/join`)
}

/**
 * 退出知识库
 */
export const leaveKnowledgeBase = (kbId) => {
  return api.post(`/knowledge-bases/${kbId}/leave`)
}

/**
 * 一键共享：将所有激活用户添加为知识库成员（仅Admin）
 */
export const shareKnowledgeBaseToAll = (kbId) => {
  return api.post(`/knowledge-bases/${kbId}/share-to-all`)
}

/**
 * 发现知识库（搜索、分类筛选）
 */
export const discoverKnowledgeBases = (params = {}) => {
  return api.get('/knowledge-bases/discover', { params })
}

/**
 * 从文档库添加文档到知识库并自动处理
 */
export const addDocumentsFromLibrary = (kbId, documentLibraryIds, config) => {
  return api.post(`/knowledge-bases/${kbId}/documents/add-from-library`, {
    document_library_ids: documentLibraryIds,
    chunk_strategy: config.chunk_strategy || 'auto',
    max_tokens_per_section: config.max_tokens_per_section || 8000,
    analysis_mode: config.analysis_mode || 'smart_segment',
    provider: config.provider || 'local',
    use_thinking: config.use_thinking || false
  })
}

/**
 * 上传文档到知识库并自动处理（已废弃，保留用于兼容）
 * @deprecated 请使用 addDocumentsFromLibrary
 */
export const uploadAndProcessDocument = (kbId, file, config) => {
  const formData = new FormData()
  formData.append('file', file)
  
  return api.post(`/knowledge-bases/${kbId}/documents/upload-and-process`, formData, {
    params: {
      chunk_strategy: config.chunk_strategy || 'level_1',
      max_tokens_per_section: config.max_tokens_per_section || 8000,
      analysis_mode: config.analysis_mode || 'smart_segment',
      provider: config.provider || 'local',
      use_thinking: config.use_thinking || false
    },
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取知识库的文档列表
 */
export const getKnowledgeBaseDocuments = (kbId, params = {}) => {
  return api.get(`/knowledge-bases/${kbId}/documents`, { params }).then(res => res)
}

/**
 * 删除知识库的文档
 */
export const deleteKnowledgeBaseDocument = (kbId, documentId) => {
  return api.delete(`/knowledge-bases/${kbId}/documents/${documentId}`)
}

