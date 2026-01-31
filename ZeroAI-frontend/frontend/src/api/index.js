import axios from 'axios'
import { getToken, removeToken } from '@/utils/auth'

// 从环境变量读取 API 基础地址，如果没有则使用默认值 '/api'
// 开发环境：可以通过 .env 文件配置
// 生产环境：通过 Docker 构建参数 VITE_API_BASE_URL 配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1800000 // 增加到 30 分钟（1800秒），因为大文档处理需要很长时间（31个章节）
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 自动添加Token到请求头
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 401未授权，清除Token并跳转到登录页
    if (error.response?.status === 401) {
      removeToken()
      // 如果不在登录页，则跳转
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    // 保留完整的错误对象，以便前端可以访问 error.response
    return Promise.reject(error)
  }
)

export default api

