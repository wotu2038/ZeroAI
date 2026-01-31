/**
 * 知识管理API
 */
import axios from 'axios'

const API_BASE = '/api/knowledge'

// ========== Community管理 ==========
export const listCommunities = async (params) => {
  const response = await axios.get(`${API_BASE}/communities`, { params })
  return response.data
}

export const deleteCommunities = async (uuids) => {
  const response = await axios.delete(`${API_BASE}/communities`, {
    data: { uuids }
  })
  return response.data
}

// ========== Episode管理 ==========
export const listEpisodes = async (params) => {
  const response = await axios.get(`${API_BASE}/episodes`, { params })
  return response.data
}

export const deleteEpisodes = async (uuids) => {
  const response = await axios.delete(`${API_BASE}/episodes`, {
    data: { uuids }
  })
  return response.data
}

// ========== 关系管理 ==========
export const listEdges = async (params) => {
  const response = await axios.get(`${API_BASE}/edges`, { params })
  return response.data
}

export const deleteEdges = async (uuids) => {
  const response = await axios.delete(`${API_BASE}/edges`, {
    data: { uuids }
  })
  return response.data
}

// ========== 实体管理 ==========
export const listEntities = async (params) => {
  const response = await axios.get(`${API_BASE}/entities`, { params })
  return response.data
}

export const deleteEntities = async (uuids) => {
  const response = await axios.delete(`${API_BASE}/entities`, {
    data: { uuids }
  })
  return response.data
}

// ========== Group管理 ==========
export const listGroups = async (params) => {
  const response = await axios.get(`${API_BASE}/groups`, { params })
  return response.data
}

export const getGroupDetail = async (group_id) => {
  const response = await axios.get(`${API_BASE}/groups/${group_id}/detail`)
  return response.data
}

export const deleteGroup = async (group_id) => {
  const response = await axios.delete(`${API_BASE}/groups/${group_id}`)
  return response.data
}

// ========== 文档列表 ==========
export const listDocuments = async () => {
  const response = await axios.get(`${API_BASE}/documents`)
  return response.data
}

