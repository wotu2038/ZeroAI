import api from './index'

/**
 * 获取模板列表
 */
export const getTemplates = (page = 1, pageSize = 10, category = null, search = null) => {
  const params = { page, page_size: pageSize }
  if (category) params.category = category
  if (search) params.search = search
  return api.get('/templates', { params })
}

/**
 * 获取模板详情
 */
export const getTemplate = (templateId) => {
  return api.get(`/templates/${templateId}`)
}

/**
 * 创建模板
 */
export const createTemplate = (templateData) => {
  return api.post('/templates', templateData)
}

/**
 * 更新模板
 */
export const updateTemplate = (templateId, templateData) => {
  return api.put(`/templates/${templateId}`, templateData)
}

/**
 * 删除模板
 */
export const deleteTemplate = (templateId) => {
  return api.delete(`/templates/${templateId}`)
}

/**
 * 校验模板
 */
export const validateTemplate = (templateData) => {
  return api.post('/templates/validate', templateData)
}

/**
 * 设置默认模板
 */
export const setDefaultTemplate = (templateId) => {
  return api.post(`/templates/${templateId}/set-default`)
}

/**
 * LLM异步生成模板
 */
export const generateTemplateAsync = (requestData) => {
  return api.post('/templates/generate-async', requestData)
}

