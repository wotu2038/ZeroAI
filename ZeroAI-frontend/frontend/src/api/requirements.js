import api from './index'

// ==================== 需求管理相关 API ====================

/**
 * 获取需求列表
 */
export const listRequirements = (limit = 50, offset = 0) => {
  return api.get('/requirements', {
    params: { limit, offset }
  })
}

/**
 * 创建需求
 */
export const createRequirement = (requirement, provider = 'qianwen') => {
  return api.post('/requirements', requirement, {
    params: { provider }
  })
}

/**
 * 获取需求详情
 */
export const getRequirement = (requirementId) => {
  return api.get(`/requirements/${requirementId}`)
}

/**
 * 删除需求
 */
export const deleteRequirement = (requirementId) => {
  return api.delete(`/requirements/${requirementId}`)
}

/**
 * 查找相似需求
 */
export const findSimilarRequirements = (query, provider = 'qianwen') => {
  return api.post('/requirements/similar', query, {
    params: { provider }
  })
}

/**
 * 生成需求文档（同步）
 */
export const generateRequirementDocument = (request, provider = 'qianwen') => {
  return api.post('/requirements/generate', request, {
    params: { provider }
  })
}

/**
 * 异步生成需求文档（使用LangGraph多Agent工作流）
 */
export const generateRequirementDocumentAsync = (request) => {
  return api.post('/requirements/generate-async', request)
}

// ==================== 智能问答相关 API ====================

/**
 * 智能问答（支持单文档、多文档、全部文档）
 * @param {string|null} groupId - 单文档模式：文档 group_id
 * @param {Array<string>|null} groupIds - 多文档模式：文档 group_id 列表
 * @param {boolean} allDocuments - 全部文档模式：是否检索全部文档
 * @param {Array} messages - 对话消息列表
 * @param {string} provider - LLM提供商
 * @param {number} temperature - 温度参数
 * @param {boolean} useThinking - 是否启用Thinking模式（仅本地大模型支持）
 * @param {string} crossEncoderMode - 交叉编码方案：'default'（默认）、'enhanced'（增强）、'smart'（智能增强）
 * @param {number|null} knowledgeBaseId - 知识库ID（用于保存对话历史）
 * @param {string|null} sessionId - 会话ID（用于Mem0记忆管理）
 */
export const qaChat = (groupId = null, groupIds = null, allDocuments = false, messages, provider = 'qianwen', temperature = 0.7, useThinking = false, crossEncoderMode = 'default', knowledgeBaseId = null, sessionId = null) => {
  const params = {}
  if (allDocuments) {
    params.all_documents = true
  } else if (groupIds && groupIds.length > 0) {
    // 多文档模式：使用 group_ids 参数（数组）
    params.group_ids = groupIds
  } else if (groupId) {
    // 单文档模式：使用 group_id 参数
    params.group_id = groupId
  }
  
  // 添加知识库ID（用于保存对话历史）
  if (knowledgeBaseId) {
    params.knowledge_base_id = knowledgeBaseId
  }
  
  // 添加会话ID（用于Mem0记忆管理）
  if (sessionId) {
    params.session_id = sessionId
  }
  
  // 自定义参数序列化器，将数组参数序列化为 FastAPI 期望的重复参数格式
  // 例如：group_ids=value1&group_ids=value2 而不是 group_ids[]=value1&group_ids[]=value2
  const paramsSerializer = (params) => {
    const parts = []
    for (const key in params) {
      if (params.hasOwnProperty(key)) {
        const value = params[key]
        if (Array.isArray(value)) {
          // 数组参数：重复键名
          value.forEach(item => {
            parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(item)}`)
          })
        } else if (value !== null && value !== undefined) {
          // 普通参数
          parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        }
      }
    }
    return parts.join('&')
  }
  
  return api.post('/requirements/qa/chat', {
    provider,
    messages,
    temperature,
    use_thinking: useThinking,
    cross_encoder_mode: crossEncoderMode
  }, { 
    params,
    paramsSerializer
  })
}

/**
 * 获取对话历史记录
 * @param {number|null} knowledgeBaseId - 知识库ID（可选，用于筛选）
 * @param {number} page - 页码
 * @param {number} pageSize - 每页数量
 */
export const getChatHistory = (knowledgeBaseId = null, page = 1, pageSize = 20) => {
  const params = { page, page_size: pageSize }
  if (knowledgeBaseId) {
    params.knowledge_base_id = knowledgeBaseId
  }
  return api.get('/requirements/qa/history', { params })
}

/**
 * 相似需求推荐
 */
export const qaSimilarRequirements = (queryText, groupId = null, limit = 5, provider = 'qianwen') => {
  let url = `/requirements/qa/similar?query_text=${encodeURIComponent(queryText)}&limit=${limit}&provider=${provider}`
  if (groupId) {
    url += `&group_id=${encodeURIComponent(groupId)}`
  }
  return api.post(url)
}

/**
 * 需求分析
 */
export const qaAnalyzeRequirement = (groupId, provider = 'qianwen') => {
  return api.post(`/requirements/qa/analyze?group_id=${encodeURIComponent(groupId)}&provider=${provider}`)
}

