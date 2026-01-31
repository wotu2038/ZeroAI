import api from './index'

export const importData = (data) => {
  return api.post('/import', data)
}

