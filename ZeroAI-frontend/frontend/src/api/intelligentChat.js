import api from './index'

// ==================== 文档入库流程 API ====================

/**
 * 步骤1: Graphiti文档级处理
 * @param {Object} params - 参数对象
 * @param {number} params.upload_id - 文档上传ID
 * @param {string} params.provider - LLM提供商
 * @param {number} params.temperature - 温度参数
 */
export const step1GraphitiEpisode = (params) => {
  return api.post('/intelligent-chat/step1/graphiti-episode', params)
}

/**
 * 获取Graphiti图谱数据
 * @param {string} group_id - 文档组ID
 */
export const getGraphitiGraph = (group_id) => {
  return api.get(`/word-document/${group_id}/graph`)
}

/**
 * 步骤2: Cognee章节级处理
 * @param {Object} params - 参数对象
 * @param {number} params.upload_id - 文档上传ID
 * @param {string} params.group_id - 文档组ID
 * @param {string} params.provider - LLM提供商
 */
export const step2CogneeBuild = (params) => {
  return api.post('/intelligent-chat/step2/cognee-build', params)
}

/**
 * 获取Cognee图谱数据
 * @param {string} group_id - 文档组ID
 */
export const getCogneeGraph = (group_id) => {
  return api.get('/intelligent-chat/step2/cognee-graph', {
    params: { group_id }
  })
}

/**
 * 步骤3: Milvus向量化处理
 * @param {Object} params - 参数对象
 * @param {number} params.upload_id - 文档上传ID
 * @param {string} params.group_id - 文档组ID
 */
export const step3MilvusVectorize = (params) => {
  return api.post('/intelligent-chat/step3/milvus-vectorize', params)
}

// ==================== 检索生成流程 API ====================

/**
 * 步骤4: Milvus快速召回
 * @param {Object} params - 参数对象
 * @param {string} params.query - 查询文本
 * @param {number} params.top_k - 返回数量
 * @param {Array<string>} params.group_ids - 文档组ID列表（可选）
 */
export const step4MilvusRecall = (params) => {
  return api.post('/intelligent-chat/step4/milvus-recall', params)
}

/**
 * 步骤5: Neo4j精筛
 * @param {Object} params - 参数对象
 * @param {Array} params.recall_results - Milvus召回结果
 * @param {string} params.query - 查询文本
 */
export const step5Neo4jRefine = (params) => {
  return api.post('/intelligent-chat/step5/neo4j-refine', params)
}

/**
 * 步骤6: Mem0记忆注入
 * @param {Object} params - 参数对象
 * @param {Array} params.refined_results - Neo4j精筛结果
 * @param {string} params.user_id - 用户ID
 * @param {string} params.session_id - 会话ID
 */
export const step6Mem0Inject = (params) => {
  return api.post('/intelligent-chat/step6/mem0-inject', params)
}

/**
 * Mem0 独立问答
 * @param {Object} params - 参数对象
 * @param {string} params.query - 用户问题
 * @param {string} params.user_id - 用户ID（可选，未登录时使用）
 * @param {string} params.session_id - 会话ID（可选）
 * @param {Array} params.conversation_history - 对话历史（可选）
 * @param {string} params.provider - LLM提供商（默认 "local"）
 * @param {number} params.temperature - 温度参数（默认 0.7）
 */
export const mem0Chat = (params) => {
  return api.post('/intelligent-chat/mem0-chat', params)
}

/**
 * 步骤7: LLM生成
 * @param {Object} params - 参数对象
 * @param {string} params.query - 用户查询
 * @param {Array} params.injected_results - Mem0注入后的结果
 * @param {string} params.provider - LLM提供商
 * @param {number} params.temperature - 温度参数
 */
export const step7LLMGenerate = (params) => {
  return api.post('/intelligent-chat/step7/llm-generate', params)
}

/**
 * 智能检索：两阶段检索策略
 * @param {Object} params - 参数对象
 * @param {string} params.query - 查询文本
 * @param {number} params.top_k - 阶段1的Top K（默认50）
 * @param {boolean} params.top3 - 是否选择Top3文档（默认true）
 * @param {Array<string>} params.group_ids - 检索范围（可选）
 * @param {boolean} params.enable_refine - 是否启用阶段2精细处理（默认true）
 * @param {boolean} params.enable_bm25 - 是否启用BM25检索（默认true）
 * @param {boolean} params.enable_graph_traverse - 是否启用图遍历（默认true）
 */
export const smartRetrieval = (params) => {
  return api.post('/intelligent-chat/smart-retrieval', params)
}

