import api from './index'

/**
 * 上传并处理 Word 文档
 */
export const uploadWordDocument = (file, provider = 'qianwen', maxTokensPerSection = 8000) => {
  const formData = new FormData()
  formData.append('file', file)
  
  return api.post('/word-document/upload', formData, {
    params: {
      provider,
      max_tokens_per_section: maxTokensPerSection
    },
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取文档的所有 Episode
 */
export const getDocumentEpisodes = (documentId, includeContent = false, provider = 'qianwen') => {
  return api.get(`/word-document/${documentId}/episodes`, {
    params: {
      include_content: includeContent,
      provider
    }
  })
}

/**
 * 获取文档列表
 */
export const getDocumentList = (provider = 'qianwen', limit = 50, offset = 0) => {
  return api.get('/word-document/', {  // 添加尾部斜杠，避免307重定向
    params: { provider, limit, offset }
  })
}

export const getDocumentGraph = (documentId, provider = 'qianwen', limit = 500) => {
  return api.get(`/word-document/${documentId}/graph`, {
    params: { provider, limit }
  })
}

/**
 * 获取文档的原始内容和解析后的全部内容
 */
export const getDocumentContent = (documentId, provider = 'qianwen') => {
  return api.get(`/word-document/${documentId}/content`, {
    params: { provider }
  })
}

/**
 * 获取原始Word文档的下载URL
 */
export const getDocumentDownloadUrl = (documentId, provider = 'qianwen') => {
  return `/api/word-document/${documentId}/download?provider=${provider}`
}

/**
 * 实时解析Word文档（从原始文档重新解析）
 */
export const getRealtimeParsedContent = (documentId, provider = 'qianwen', maxTokensPerSection = 8000) => {
  return api.get(`/word-document/${documentId}/realtime-parse`, {
    params: { provider, max_tokens_per_section: maxTokensPerSection }
  })
}

/**
 * 获取文档的所有版本
 */
export const getDocumentVersions = (baseDocumentId, provider = 'qianwen') => {
  return api.get(`/word-document/${baseDocumentId}/versions`, {
    params: { provider }
  })
}

/**
 * 对比两个版本的差异
 */
export const compareDocumentVersions = (baseDocumentId, version1, version2, provider = 'qianwen') => {
  return api.get(`/word-document/${baseDocumentId}/compare`, {
    params: { version1, version2, provider }
  })
}

/**
 * 删除文档及其所有相关的Episode、Entity和Relationship
 */
export const deleteDocument = (documentId, provider = 'qianwen') => {
  return api.delete(`/word-document/${documentId}`, {
    params: { provider }
  })
}

