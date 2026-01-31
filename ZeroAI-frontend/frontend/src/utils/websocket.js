/**
 * WebSocket 工具类 - 用于任务进度实时推送
 */

class TaskWebSocket {
  constructor() {
    this.socket = null
    this.taskId = null
    this.callbacks = {
      onProgress: null,
      onComplete: null,
      onError: null,
      onClose: null
    }
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 3
    this.reconnectDelay = 2000
  }

  /**
   * 连接到任务进度 WebSocket
   * @param {string} taskId - 任务ID
   * @param {Object} callbacks - 回调函数
   */
  connect(taskId, callbacks = {}) {
    this.taskId = taskId
    this.callbacks = { ...this.callbacks, ...callbacks }

    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/ws/task/${taskId}`

    console.log('连接 WebSocket:', wsUrl)

    try {
      this.socket = new WebSocket(wsUrl)

      this.socket.onopen = () => {
        console.log('WebSocket 已连接')
        this.reconnectAttempts = 0
      }

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.handleMessage(data)
        } catch (e) {
          console.error('解析 WebSocket 消息失败:', e)
        }
      }

      this.socket.onerror = (error) => {
        console.error('WebSocket 错误:', error)
        if (this.callbacks.onError) {
          this.callbacks.onError(error)
        }
      }

      this.socket.onclose = (event) => {
        console.log('WebSocket 已关闭:', event.code, event.reason)
        if (this.callbacks.onClose) {
          this.callbacks.onClose(event)
        }
        
        // 尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts && event.code !== 1000) {
          this.reconnectAttempts++
          console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
          setTimeout(() => {
            this.connect(this.taskId, this.callbacks)
          }, this.reconnectDelay)
        }
      }
    } catch (error) {
      console.error('创建 WebSocket 失败:', error)
      if (this.callbacks.onError) {
        this.callbacks.onError(error)
      }
    }
  }

  /**
   * 处理接收到的消息
   * @param {Object} data - 消息数据
   */
  handleMessage(data) {
    const { type, progress, message, status, result, error } = data

    switch (type) {
      case 'progress':
        if (this.callbacks.onProgress) {
          this.callbacks.onProgress({
            progress: progress || 0,
            message: message || '',
            status: status || 'processing'
          })
        }
        break

      case 'complete':
        if (this.callbacks.onComplete) {
          this.callbacks.onComplete({
            status: 'completed',
            result: result,
            message: message
          })
        }
        this.disconnect()
        break

      case 'error':
        if (this.callbacks.onError) {
          this.callbacks.onError({
            status: 'failed',
            error: error || message,
            message: message
          })
        }
        this.disconnect()
        break

      default:
        console.log('未知消息类型:', type, data)
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.socket) {
      this.socket.close(1000, '正常关闭')
      this.socket = null
    }
  }

  /**
   * 检查连接状态
   */
  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN
  }
}

// 导出单例
export const taskWebSocket = new TaskWebSocket()

// 导出工具函数
export const connectToTask = (taskId, callbacks) => {
  const ws = new TaskWebSocket()
  ws.connect(taskId, callbacks)
  return ws
}

export default TaskWebSocket

