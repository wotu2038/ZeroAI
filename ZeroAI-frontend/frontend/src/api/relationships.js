import api from './index'

export const getRelationships = (params) => {
  return api.get('/relationships', { params })
}

export const getRelationship = (id) => {
  return api.get(`/relationships/${id}`)
}

export const createRelationship = (data) => {
  return api.post('/relationships', data)
}

export const updateRelationship = (id, data) => {
  return api.put(`/relationships/${id}`, data)
}

export const deleteRelationship = (id) => {
  return api.delete(`/relationships/${id}`)
}

export const getEntityRelationships = (entityId) => {
  return api.get(`/relationships/entity/${entityId}`)
}

export const getRelationshipTypes = () => {
  return api.get('/relationships/types')
}

