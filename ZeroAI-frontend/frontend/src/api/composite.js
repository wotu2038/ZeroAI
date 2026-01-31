import api from './index'

/**
 * 创建组合
 */
export const createComposite = (compositeData) => {
  return api.post('/composite/create', compositeData)
}

/**
 * 获取组合列表
 */
export const getCompositeList = (type = null) => {
  return api.get('/composite/list', {
    params: type ? { type } : {}
  })
}

/**
 * 获取组合详情
 */
export const getComposite = (compositeUuid) => {
  return api.get(`/composite/${compositeUuid}`)
}

/**
 * 更新组合
 */
export const updateComposite = (compositeUuid, compositeData) => {
  return api.put(`/composite/${compositeUuid}`, compositeData)
}

/**
 * 删除组合
 */
export const deleteComposite = (compositeUuid) => {
  return api.delete(`/composite/${compositeUuid}`)
}

/**
 * 获取组合图谱数据
 */
export const getCompositeGraph = (compositeUuid, limit = 2000) => {
  return api.get(`/composite/${compositeUuid}/graph`, {
    params: { limit }
  })
}

