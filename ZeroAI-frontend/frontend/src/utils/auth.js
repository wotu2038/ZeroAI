/**
 * 认证工具函数
 */

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'current_user'

/**
 * 保存Token
 */
export const setToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 获取Token
 */
export const getToken = () => {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 移除Token
 */
export const removeToken = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/**
 * 保存用户信息
 */
export const setUser = (user) => {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

/**
 * 获取用户信息
 */
export const getUser = () => {
  const userStr = localStorage.getItem(USER_KEY)
  if (!userStr) return null
  try {
    return JSON.parse(userStr)
  } catch (e) {
    return null
  }
}

/**
 * 检查是否已登录
 */
export const isAuthenticated = () => {
  return !!getToken()
}

/**
 * 检查用户是否为Admin
 */
export const isAdmin = () => {
  const user = getUser()
  return user && user.role === 'admin'
}

