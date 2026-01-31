import api from './index'

/**
 * ==================== 文件夹管理 ====================
 */

/**
 * 获取文件夹列表（树结构）
 */
export const getFolders = () => {
  return api.get('/document-library/folders/tree')
}

/**
 * 创建文件夹
 */
export const createFolder = (data) => {
  return api.post('/document-library/folders', data)
}

/**
 * 更新文件夹
 */
export const updateFolder = (folderId, data) => {
  return api.put(`/document-library/folders/${folderId}`, data)
}

/**
 * 删除文件夹
 */
export const deleteFolder = (folderId) => {
  return api.delete(`/document-library/folders/${folderId}`)
}

/**
 * ==================== 文档管理 ====================
 */

/**
 * 获取文档列表
 */
export const getDocuments = (params = {}) => {
  return api.get('/document-library/documents', { params })
}

/**
 * 上传文档到文档库
 */
export const uploadDocument = (file, folderId = null) => {
  const formData = new FormData()
  formData.append('file', file)
  if (folderId) {
    formData.append('folder_id', folderId)
  }
  return api.post('/document-library/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 批量上传文档
 */
export const uploadDocumentsBatch = (files, folderId = null) => {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  if (folderId) {
    formData.append('folder_id', folderId)
  }
  return api.post('/document-library/documents/upload/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取文档详情
 */
export const getDocument = (documentId) => {
  return api.get(`/document-library/documents/${documentId}`)
}

/**
 * 删除文档
 */
export const deleteDocument = (documentId) => {
  return api.delete(`/document-library/documents/${documentId}`)
}

/**
 * 批量删除文档
 */
export const deleteDocumentsBatch = (documentIds) => {
  return api.post('/document-library/documents/batch/delete', {
    document_ids: documentIds
  })
}

/**
 * 移动文档到文件夹
 */
export const moveDocument = (documentId, folderId) => {
  return api.put(`/document-library/documents/${documentId}/move`, {
    folder_id: folderId
  })
}

/**
 * 批量移动文档
 */
export const moveDocumentsBatch = (documentIds, folderId) => {
  return api.post('/document-library/documents/batch/move', {
    document_ids: documentIds,
    folder_id: folderId
  })
}

/**
 * ==================== 文档-知识库关联 ====================
 */

/**
 * 将文档添加到知识库
 */
export const addDocumentToKnowledgeBase = (documentId, knowledgeBaseId) => {
  return api.post(`/document-library/documents/${documentId}/knowledge-bases`, {
    knowledge_base_id: knowledgeBaseId
  })
}

/**
 * 批量添加文档到知识库
 */
export const addDocumentsToKnowledgeBaseBatch = (documentIds, knowledgeBaseId) => {
  return api.post('/document-library/documents/batch/add-to-knowledge-base', {
    document_ids: documentIds,
    knowledge_base_id: knowledgeBaseId
  })
}

/**
 * 从知识库移除文档
 */
export const removeDocumentFromKnowledgeBase = (documentId, knowledgeBaseId) => {
  return api.delete(`/document-library/documents/${documentId}/knowledge-bases/${knowledgeBaseId}`)
}

/**
 * 获取文档关联的知识库列表
 */
export const getDocumentKnowledgeBases = (documentId) => {
  return api.get(`/document-library/documents/${documentId}/knowledge-bases`)
}

/**
 * ==================== 统计信息 ====================
 */

/**
 * 获取文档库统计信息
 */
export const getStatistics = () => {
  return api.get('/document-library/statistics')
}

/**
 * ==================== 搜索 ====================
 */

/**
 * 搜索文档
 */
export const searchDocuments = (keyword, params = {}) => {
  return api.get('/document-library/documents/search', {
    params: { keyword, ...params }
  })
}

