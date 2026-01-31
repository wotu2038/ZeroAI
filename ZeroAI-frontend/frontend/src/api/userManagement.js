/**
 * 用户管理API
 */
import api from './index'

/**
 * 获取用户列表
 */
export const getUsers = (params) => {
  return api.get('/user-management', { params })
}

/**
 * 获取用户详情
 */
export const getUser = (userId) => {
  return api.get(`/user-management/${userId}`)
}

/**
 * 创建用户
 */
export const createUser = (data) => {
  return api.post('/user-management', data)
}

/**
 * 更新用户
 */
export const updateUser = (userId, data) => {
  return api.put(`/user-management/${userId}`, data)
}

/**
 * 删除用户
 */
export const deleteUser = (userId) => {
  return api.delete(`/user-management/${userId}`)
}

/**
 * 重置用户密码
 */
export const resetPassword = (userId, newPassword) => {
  return api.post(`/user-management/${userId}/reset-password`, {
    new_password: newPassword
  })
}

