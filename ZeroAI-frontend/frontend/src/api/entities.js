import api from './index'

export const getEntities = (params) => {
  return api.get('/entities', { params })
}

export const getEntity = (id) => {
  return api.get(`/entities/${id}`)
}

export const createEntity = (data) => {
  return api.post('/entities', data)
}

export const updateEntity = (id, data) => {
  return api.put(`/entities/${id}`, data)
}

export const deleteEntity = (id) => {
  return api.delete(`/entities/${id}`)
}

export const searchEntities = (keyword, limit = 20) => {
  return api.get('/entities/search', { params: { keyword, limit } })
}

export const getEntityTypes = () => {
  return api.get('/entities/types')
}

