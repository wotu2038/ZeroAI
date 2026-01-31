import api from './index'
import axios from 'axios'

/**
 * 提交异步任务（步骤5：处理文档）
 */
export const submitTask = (data) => {
  return api.post('/tasks/submit', data)
}

/**
 * 查询任务状态
 */
export const getTask = (taskId) => {
  return api.get(`/tasks/${taskId}`)
}

/**
 * 查询任务列表
 */
export const getTaskList = (page = 1, pageSize = 20, status = null, uploadId = null) => {
  const params = { page, page_size: pageSize }
  if (status) {
    params.status = status
  }
  if (uploadId) {
    params.upload_id = uploadId
  }
  return api.get('/tasks', { params })
}

/**
 * 取消任务
 */
export const cancelTask = (taskId) => {
  return api.post(`/tasks/${taskId}/cancel`)
}

/**
 * 下载任务生成的文档（DOCX格式）
 */
export const downloadTaskDocumentDocx = async (taskId) => {
  // 直接使用axios，绕过响应拦截器，因为需要blob数据
  const response = await axios.get(`/api/tasks/${taskId}/download-docx`, {
    responseType: 'blob',
    baseURL: ''  // 使用相对路径
  })
  return response.data
}

