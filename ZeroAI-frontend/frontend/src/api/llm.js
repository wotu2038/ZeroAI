import api from './index'

export const chat = (data) => {
  return api.post('/llm/chat', data)
}

export const extractEntities = (data) => {
  // 构建请求数据，包含可选的元数据
  const requestData = {
    provider: data.provider,
    text: data.text
  }
  if (data.metadata) {
    requestData.metadata = data.metadata
  }
  return api.post('/llm/extract', requestData)
}

export const getProviders = () => {
  return api.get('/llm/providers')
}

