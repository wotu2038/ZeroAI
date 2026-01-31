import api from './index'

/**
 * 用户注册
 */
export const register = (data) => {
  return api.post('/auth/register', data)
}

/**
 * 用户登录
 */
export const login = (data) => {
  return api.post('/auth/login', data)
}

/**
 * 获取当前用户信息
 */
export const getCurrentUser = () => {
  return api.get('/auth/me')
}

