import api from './index'

/**
 * 上传文档（仅验证和保存）
 */
export const uploadDocument = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  return api.post('/document-upload/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取文档列表（支持分页、搜索、筛选）
 */
export const getDocumentUploadList = (page = 1, pageSize = 10, search = null, status = null) => {
  const params = {
    page,
    page_size: pageSize
  }
  if (search) {
    params.search = search
  }
  if (status) {
    params.status = status
  }
  
  return api.get('/document-upload/list', { params })
}

/**
 * 获取文档详情
 */
export const getDocumentUpload = (documentId) => {
  return api.get(`/document-upload/${documentId}`)
}

/**
 * 删除文档
 */
export const deleteDocumentUpload = (documentId) => {
  return api.delete(`/document-upload/${documentId}`)
}

/**
 * 解析文档（仅解析，不保存到Neo4j）
 */
export const parseDocument = (uploadId, maxTokensPerSection = 8000) => {
  return api.post(`/document-upload/${uploadId}/parse`, null, {
    params: {
      max_tokens_per_section: maxTokensPerSection
    }
  })
}

/**
 * 生成版本信息（提取版本号、生成group_id）
 */
export const generateVersion = (uploadId, customGroupId = null) => {
  const params = {}
  if (customGroupId) {
    params.custom_group_id = customGroupId
  }
  return api.post(`/document-upload/${uploadId}/version`, null, { params })
}

/**
 * 更新版本信息（版本号、group_id）
 */
export const updateVersion = (uploadId, version, versionNumber, groupId) => {
  return api.put(`/document-upload/${uploadId}/version`, {
    version,
    version_number: versionNumber,
    group_id: groupId
  })
}

/**
 * 章节分块（支持多种策略）
 * @param {number} uploadId - 文档ID
 * @param {string} strategy - 分块策略: level_1, level_2, fixed_token, no_split
 * @param {number} maxTokensPerSection - 每个块的最大token数
 * @param {boolean} saveChunks - 是否保存分块结果
 */
export const splitDocument = (uploadId, strategy = 'level_1', maxTokensPerSection = 8000, saveChunks = true) => {
  return api.post(`/document-upload/${uploadId}/split`, null, {
    params: {
      strategy,
      max_tokens_per_section: maxTokensPerSection,
      save_chunks: saveChunks
    }
  })
}

/**
 * 处理文档并保存到Neo4j（方案B：混合使用parsed_content和summary_content）
 */
export const processDocument = (uploadId, provider = 'qianwen', maxTokensPerSection = 8000) => {
  return api.post(`/document-upload/${uploadId}/process`, null, {
    params: {
      provider,
      max_tokens_per_section: maxTokensPerSection
    }
  })
}

/**
 * 获取解析后的完整对应文档（parsed_content.md）
 */
export const getParsedContent = (uploadId) => {
  return api.get(`/document-upload/${uploadId}/parsed-content`)
}

/**
 * 获取解析后的总结文档（summary_content.md）
 */
export const getSummaryContent = (uploadId) => {
  return api.get(`/document-upload/${uploadId}/summary-content`)
}

/**
 * 获取解析后的结构化数据（structured_content.json）
 */
export const getStructuredContent = (uploadId) => {
  return api.get(`/document-upload/${uploadId}/structured-content`)
}

/**
 * 获取分块结果（chunks.json）
 */
export const getChunks = (uploadId) => {
  return api.get(`/document-upload/${uploadId}/chunks`)
}

/**
 * 构建Community（当前文档或跨文档）- 同步API（已废弃）
 * @deprecated 请使用 buildCommunitiesAsync
 */
export const buildCommunities = (uploadId, scope, groupIds = null, provider = 'qianwen') => {
  const data = {
    scope
  }
  if (scope === 'cross' && groupIds && groupIds.length > 0) {
    data.group_ids = groupIds
  }
  return api.post(`/document-upload/${uploadId}/build-communities`, data, {
    params: {
      provider
    }
  })
}

/**
 * 异步构建Community（当前文档或跨文档）
 * @param {number} uploadId - 文档ID
 * @param {string} scope - 构建范围: 'current' 或 'cross'
 * @param {Array<string>} groupIds - 跨文档时提供的group_id列表（可选）
 * @param {string} provider - LLM提供商
 * @param {boolean} useThinking - 是否启用Thinking模式（仅本地大模型支持）
 */
export const buildCommunitiesAsync = (uploadId, scope, groupIds = null, provider = 'local', useThinking = false) => {
  const data = {
    scope
  }
  if (scope === 'cross' && groupIds && groupIds.length > 0) {
    data.group_ids = groupIds
  }
  return api.post(`/document-upload/${uploadId}/build-communities-async`, data, {
    params: {
      provider,
      use_thinking: useThinking
    }
  })
}

/**
 * 获取所有已有的 Group ID 列表（用于下拉选择）
 * @param {string} search - 搜索关键词（模糊匹配）
 * @param {number} limit - 返回数量限制
 */
export const getGroupIds = (search = null, limit = 50) => {
  const params = { limit }
  if (search) {
    params.search = search
  }
  return api.get('/document-upload/group-ids', { params })
}

