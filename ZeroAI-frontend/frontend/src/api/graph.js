import api from './index'
import { getEntity } from './entities'
import { getRelationship } from './relationships'

export const getGraphData = (limit = 100) => {
  return api.get('/graph/data', { params: { limit } })
}

export const executeGraphQuery = (query) => {
  return api.post('/graph/query', { query })
}

export const getGraphStats = () => {
  return api.get('/graph/stats')
}

export const getNodeDetails = (nodeId) => {
  // 通过实体API获取节点详情
  return getEntity(nodeId)
}

export const getEdgeDetails = (edgeId) => {
  // 通过关系API获取边详情
  return getRelationship(edgeId)
}

export const retrieveGraph = (query, provider = 'qianwen', limit = 10) => {
  // 使用Graphiti进行语义检索
  return api.post('/graph/retrieve-body', {
    query,
    provider,
    limit
  })
}

export const findPaths = (source, target = null, maxDepth = 10, limit = 100) => {
  // 查找关系路径
  return api.post('/graph/find-paths', {
    source,
    target,
    max_depth: maxDepth,
    limit
  })
}

