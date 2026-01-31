<template>
  <a-card title="智能对话">
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="chat" tab="智能对话">
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="选择LLM">
            <a-space>
              <a-radio-group v-model:value="selectedProvider">
                <a-radio value="qianwen">千问</a-radio>
                <a-radio value="local">本地大模型</a-radio>
              </a-radio-group>
              <a-slider
                v-model:value="temperature"
                :min="0"
                :max="2"
                :step="0.1"
                style="width: 200px; margin-left: 24px"
                :tooltip-formatter="(val) => `温度: ${val}`"
              />
              <span style="color: #999; font-size: 12px">温度: {{ temperature }}</span>
            </a-space>
          </a-form-item>
        </a-form>

        <!-- 对话区域 -->
        <div
          style="
            border: 1px solid #d9d9d9;
            border-radius: 8px;
            padding: 16px;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
            background: #fafafa;
            margin-bottom: 16px;
          "
          ref="chatContainer"
        >
          <!-- 空状态 -->
          <a-empty
            v-if="messages.length === 0"
            description="开始对话吧！系统会自动从知识图谱检索相关信息来回答您的问题。"
            style="margin: 60px 0"
          />

          <!-- 消息列表 -->
          <div v-for="(msg, index) in messages" :key="index" style="margin-bottom: 24px">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" style="display: flex; justify-content: flex-end; margin-bottom: 8px">
              <div
                style="
                  max-width: 70%;
                  background: #1890ff;
                  color: white;
                  padding: 12px 16px;
                  border-radius: 12px 12px 4px 12px;
                  word-wrap: break-word;
                "
              >
                <div style="white-space: pre-wrap">{{ msg.content }}</div>
                <div style="font-size: 11px; opacity: 0.8; margin-top: 4px">
                  {{ formatTime(msg.timestamp) }}
                </div>
              </div>
            </div>

            <!-- AI消息 -->
            <div v-else style="display: flex; justify-content: flex-start; margin-bottom: 8px">
              <div style="max-width: 70%">
                <!-- AI回答内容 -->
                <div
                  style="
                    background: white;
                    border: 1px solid #e8e8e8;
                    padding: 12px 16px;
                    border-radius: 12px 12px 12px 4px;
                    word-wrap: break-word;
                    margin-bottom: 8px;
                  "
                >
                  <div style="white-space: pre-wrap">{{ msg.content }}</div>
                  <div style="font-size: 11px; color: #999; margin-top: 8px; display: flex; align-items: center; gap: 8px">
                    <span>{{ formatTime(msg.timestamp) }}</span>
                    <a-tag v-if="msg.has_context" color="green" size="small">基于知识图谱</a-tag>
                    <a-tag v-else color="orange" size="small">通用回答</a-tag>
                    <a-button
                      type="link"
                      size="small"
                      style="padding: 0; height: auto"
                      @click="copyMessage(msg.content)"
                    >
                      复制
                    </a-button>
                  </div>
                </div>

                <!-- 检索结果面板 -->
                <a-collapse
                  v-if="msg.retrieval_results && msg.retrieval_results.length > 0"
                  :bordered="false"
                  style="background: white; border: 1px solid #e8e8e8; border-radius: 8px"
                >
                  <template #expandIcon="{ isActive }">
                    <CaretRightOutlined :rotate="isActive ? 90 : 0" />
                  </template>
                  <a-collapse-panel
                    :key="index"
                    :header="`检索结果 (${msg.retrieval_count} 个，耗时 ${msg.retrieval_time?.toFixed(0) || 0}ms)`"
                  >
                    <div style="max-height: 300px; overflow-y: auto">
                      <!-- 实体列表 -->
                      <div v-if="getEntities(msg.retrieval_results).length > 0" style="margin-bottom: 16px">
                        <a-typography-title :level="5" style="margin-bottom: 8px">实体</a-typography-title>
                        <a-list
                          :data-source="getEntities(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item style="padding: 8px 0">
                              <!-- 图片Episode特殊显示 -->
                              <div v-if="isImageEpisode(item)" style="width: 100%;">
                                <a-alert 
                                  message="图片Episode" 
                                  type="info" 
                                  show-icon 
                                  size="small"
                                  style="margin-bottom: 8px;"
                                />
                                <div v-if="getImageInfo(item)" style="text-align: center; margin-bottom: 8px;">
                                  <img 
                                    :src="getImageInfo(item).url" 
                                    :alt="getImageInfo(item).description || '图片'"
                                    style="max-width: 100%; max-height: 300px; border: 1px solid #ddd; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
                                    @error="handleImageError"
                                  />
                                  <div style="margin-top: 4px; color: #666; font-size: 12px;">
                                    {{ getImageInfo(item).description || '图片' }}
                                  </div>
                                </div>
                              </div>
                              
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag :color="getTypeColor(item.labels?.[0])" size="small">
                                      {{ item.labels?.[0] || 'Entity' }}
                                    </a-tag>
                                    <strong>{{ item.properties?.name || '未知' }}</strong>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ (item.score * 100).toFixed(1) }}%
                                    </a-tag>
                                  </a-space>
                                </template>
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <span v-for="(value, key) in item.properties" :key="key" style="margin-right: 12px">
                                      <span v-if="key !== 'name' && key !== 'content' && key !== 'group_id'">{{ key }}: {{ formatValue(value) }}</span>
                                    </span>
                                  </div>
                                </template>
                              </a-list-item-meta>
                              <template #actions>
                                <a-button type="link" size="small" @click="viewInGraph(item)">查看</a-button>
                              </template>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>

                      <!-- 关系列表 -->
                      <div v-if="getRelationships(msg.retrieval_results).length > 0">
                        <a-typography-title :level="5" style="margin-bottom: 8px">关系</a-typography-title>
                        <a-list
                          :data-source="getRelationships(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item style="padding: 8px 0">
                              <!-- 如果关系的source或target是图片节点，显示图片 -->
                              <div v-if="isImageNodeName(item.source_name) || isImageNodeName(item.target_name)" style="width: 100%; margin-bottom: 8px;">
                                <div v-for="(imageNode, idx) in getImageNodesFromRelationship(item)" :key="idx" style="margin-bottom: 8px;">
                                  <a-alert 
                                    :message="`图片: ${imageNode.name}`" 
                                    type="info" 
                                    show-icon 
                                    size="small"
                                    style="margin-bottom: 8px;"
                                  />
                                  <div v-if="imageNode.url" style="text-align: center;">
                                    <img 
                                      :src="imageNode.url" 
                                      :alt="imageNode.name"
                                      style="max-width: 100%; max-height: 300px; border: 1px solid #ddd; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
                                      @error="handleImageError"
                                    />
                                    <div style="margin-top: 4px; color: #666; font-size: 12px;">
                                      {{ imageNode.name }}
                                    </div>
                                  </div>
                                </div>
                              </div>
                              
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag color="blue" size="small">{{ item.rel_type || item.type }}</a-tag>
                                    <span>
                                      <strong>{{ item.source_name || `节点${item.source}` }}</strong>
                                      <ArrowRightOutlined style="margin: 0 8px" />
                                      <strong>{{ item.target_name || `节点${item.target}` }}</strong>
                                    </span>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ (item.score * 100).toFixed(1) }}%
                                    </a-tag>
                                  </a-space>
                                </template>
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <span v-for="(value, key) in item.properties" :key="key" style="margin-right: 12px">
                                      <span v-if="key !== 'id'">{{ key }}: {{ formatValue(value) }}</span>
                                    </span>
                                  </div>
                                </template>
                              </a-list-item-meta>
                              <template #actions>
                                <a-button type="link" size="small" @click="viewInGraph(item)">查看</a-button>
                              </template>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>
                    </div>
                  </a-collapse-panel>
                </a-collapse>

                <!-- 无检索结果提示 -->
                <a-alert
                  v-else-if="!msg.has_context"
                  message="未检索到知识图谱信息"
                  description="本次回答基于LLM的通用知识，未使用知识图谱数据。"
                  type="warning"
                  show-icon
                  style="margin-top: 8px"
                  size="small"
                />
              </div>
            </div>
          </div>

          <!-- 加载状态 -->
          <div v-if="chatting" style="text-align: center; padding: 20px">
            <a-spin size="large">
              <template #indicator>
                <LoadingOutlined style="font-size: 24px" spin />
              </template>
            </a-spin>
            <div style="margin-top: 12px; color: #999">
              {{ retrievalStatus }}
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <a-form :label-col="{ span: 0 }" :wrapper-col="{ span: 24 }">
          <a-form-item>
            <a-textarea
              v-model:value="inputMessage"
              :rows="3"
              placeholder="输入你的问题...（系统会自动从知识图谱检索相关信息）"
              @pressEnter="handleSendMessage"
              :disabled="chatting"
            />
          </a-form-item>
          <a-form-item>
            <a-space>
              <a-button type="primary" @click="handleSendMessage" :loading="chatting" :disabled="!inputMessage.trim()">
                <template #icon><SendOutlined /></template>
                发送
              </a-button>
              <a-button @click="handleClear">清空对话</a-button>
              <a-button @click="handleExport">导出对话</a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </a-tab-pane>

      <a-tab-pane key="settings" tab="设置">
        <a-alert
          message="LLM配置说明"
          description="请在环境变量或配置文件中设置相应的API密钥。"
          type="info"
          style="margin-bottom: 24px"
        />
        <a-descriptions title="当前配置" :column="1" bordered>
          <a-descriptions-item label="可用提供商">
            <a-tag v-for="provider in availableProviders" :key="provider" color="blue" style="margin-right: 8px">
              {{ provider === 'qianwen' ? '千问' : provider === 'local' ? '本地大模型' : provider }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="Embedding服务">
            Ollama (bge-large-zh-v1.5)
          </a-descriptions-item>
          <a-descriptions-item label="检索策略">
            Graphiti 语义搜索 → 关键词搜索 → LLM 生成回答
          </a-descriptions-item>
        </a-descriptions>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  SendOutlined,
  LoadingOutlined,
  CaretRightOutlined,
  ArrowRightOutlined
} from '@ant-design/icons-vue'
import { chat, getProviders } from '../api/llm'

const router = useRouter()
const activeTab = ref('chat')
const selectedProvider = ref('qianwen')
const temperature = ref(0.7)
const messages = ref([])
const inputMessage = ref('')
const chatting = ref(false)
const availableProviders = ref([])
const retrievalStatus = ref('正在检索知识图谱...')
const chatContainer = ref(null)

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

const getTypeColor = (type) => {
  const colors = {
    Person: 'blue',
    Organization: 'green',
    Location: 'orange',
    Concept: 'purple',
    Event: 'pink',
    Product: 'cyan',
    Technology: 'geekblue',
    Entity: 'default'
  }
  return colors[type] || 'default'
}

const getEntities = (results) => {
  if (!results) return []
  return results.filter((r) => r.type === 'node')
}

const getRelationships = (results) => {
  if (!results) return []
  return results.filter((r) => r.type === 'edge')
}

// 判断是否是图片Episode
const isImageEpisode = (item) => {
  if (!item) return false
  const labels = item.labels || []
  const name = item.properties?.name || ''
  return labels.includes('Episodic') && name.includes('图片')
}

// 从图片Episode中提取图片信息
const getImageInfo = (item) => {
  if (!isImageEpisode(item)) return null
  
  const props = item.properties || {}
  const name = props.name || ''
  const groupId = props.group_id || ''
  
  // 从名称中提取图片编号
  const nameMatch = name.match(/图片_(\d+)/)
  if (!nameMatch || !groupId) return null
  
  const imageNumber = nameMatch[1]
  const imageId = `image_${imageNumber}`
  
  // 提取描述
  let description = ''
  const descMatch = name.match(/图片_\d+_(.+)/)
  if (descMatch) {
    description = descMatch[1].trim()
  } else {
    description = `图片 ${imageNumber}`
  }
  
  // 构建图片URL
  const imageUrl = `/api/word-document/${groupId}/images/${imageId}?provider=qianwen`
  
  return {
    imageId,
    description,
    documentId: groupId,
    url: imageUrl
  }
}

const handleImageError = (event) => {
  console.error('图片加载失败:', event.target.src)
  message.error('图片加载失败')
}

// 判断节点名称是否是图片Episode
const isImageNodeName = (name) => {
  if (!name) return false
  return name.includes('图片') && (name.includes('图片_') || name.match(/图片\s*\d+/))
}

// 从关系中提取图片节点信息
const getImageNodesFromRelationship = (item) => {
  const imageNodes = []
  
  // 检查source节点
  if (isImageNodeName(item.source_name)) {
    const imageInfo = extractImageInfoFromName(item.source_name, item.source_properties?.group_id)
    if (imageInfo) {
      imageNodes.push({
        name: item.source_name,
        ...imageInfo
      })
    }
  }
  
  // 检查target节点
  if (isImageNodeName(item.target_name)) {
    const imageInfo = extractImageInfoFromName(item.target_name, item.target_properties?.group_id)
    if (imageInfo) {
      imageNodes.push({
        name: item.target_name,
        ...imageInfo
      })
    }
  }
  
  return imageNodes
}

// 从节点名称中提取图片信息
const extractImageInfoFromName = (name, groupId) => {
  if (!name || !groupId) return null
  
  // 从名称中提取图片编号
  const nameMatch = name.match(/图片[_\s]*(\d+)/)
  if (!nameMatch) return null
  
  const imageNumber = nameMatch[1]
  const imageId = `image_${imageNumber}`
  
  // 提取描述
  let description = ''
  const descMatch = name.match(/图片[_\s]*\d+[_\s]*(.+)/)
  if (descMatch) {
    description = descMatch[1].trim()
  } else {
    description = `图片 ${imageNumber}`
  }
  
  // 构建图片URL
  const imageUrl = `/api/word-document/${groupId}/images/${imageId}?provider=qianwen`
  
  return {
    imageId,
    description,
    documentId: groupId,
    url: imageUrl
  }
}

const copyMessage = (content) => {
  navigator.clipboard.writeText(content).then(() => {
    message.success('已复制到剪贴板')
  })
}

const viewInGraph = (item) => {
  if (item.type === 'node') {
    router.push({
      name: 'graph',
      query: {
        highlight: item.id,
        type: 'node'
      }
    })
  } else {
    router.push({
      name: 'graph',
      query: {
        highlight: `${item.source}-${item.target}`,
        type: 'edge'
      }
    })
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const handleSendMessage = async () => {
  if (!inputMessage.value.trim()) {
    message.warning('请输入消息')
    return
  }

  const userMessage = inputMessage.value.trim()
  const userMsgObj = {
    role: 'user',
    content: userMessage,
    timestamp: Date.now()
  }
  messages.value.push(userMsgObj)
  inputMessage.value = ''

  chatting.value = true
  retrievalStatus.value = '正在检索知识图谱...'
  scrollToBottom()

  try {
    // 更新状态
    retrievalStatus.value = '正在使用 Graphiti 进行语义检索...'

    const response = await chat({
      provider: selectedProvider.value,
      messages: messages.value.map((m) => ({ role: m.role, content: m.content })),
      temperature: temperature.value
    })

    retrievalStatus.value = response.has_context
      ? `检索完成，找到 ${response.retrieval_count} 个相关结果`
      : '未检索到相关知识图谱信息'

    // 添加AI回答
    messages.value.push({
      role: 'assistant',
      content: response.content,
      retrieval_results: response.retrieval_results || [],
      retrieval_count: response.retrieval_count || 0,
      retrieval_time: response.retrieval_time,
      has_context: response.has_context || false,
      timestamp: Date.now()
    })

    if (response.has_context) {
      message.success(`基于 ${response.retrieval_count} 个检索结果生成回答`)
    } else {
      message.warning('未检索到相关知识图谱信息，使用通用知识回答')
    }
  } catch (error) {
    message.error('发送失败: ' + (error.response?.data?.detail || error.message))
    // 移除用户消息
    messages.value.pop()
  } finally {
    chatting.value = false
    retrievalStatus.value = ''
    scrollToBottom()
  }
}

const handleClear = () => {
  messages.value = []
  inputMessage.value = ''
  message.info('对话已清空')
}

const handleExport = () => {
  if (messages.value.length === 0) {
    message.warning('没有对话内容可导出')
    return
  }

  const exportData = {
    timestamp: new Date().toISOString(),
    provider: selectedProvider.value,
    temperature: temperature.value,
    messages: messages.value.map((m) => ({
      role: m.role,
      content: m.content,
      has_context: m.has_context,
      retrieval_count: m.retrieval_count,
      timestamp: m.timestamp
    }))
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `对话记录_${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  message.success('对话记录已导出')
}

const loadProviders = async () => {
  try {
    availableProviders.value = await getProviders()
    if (availableProviders.value.length > 0 && !availableProviders.value.includes(selectedProvider.value)) {
      selectedProvider.value = availableProviders.value[0]
    }
  } catch (error) {
    console.error('获取提供商失败:', error)
  }
}

onMounted(() => {
  loadProviders()
  // 加载本地存储的对话历史
  const savedMessages = localStorage.getItem('llm_chat_history')
  if (savedMessages) {
    try {
      const parsed = JSON.parse(savedMessages)
      if (Array.isArray(parsed) && parsed.length > 0) {
        messages.value = parsed
      }
    } catch (e) {
      console.error('加载对话历史失败:', e)
    }
  }
})

// 保存对话历史到本地存储
import { watch } from 'vue'
watch(
  messages,
  (newMessages) => {
    if (newMessages.length > 0) {
      localStorage.setItem('llm_chat_history', JSON.stringify(newMessages))
    }
  },
  { deep: true }
)
</script>

<style scoped>
/* 自定义滚动条样式 */
div[style*='overflow-y: auto']::-webkit-scrollbar {
  width: 6px;
}

div[style*='overflow-y: auto']::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

div[style*='overflow-y: auto']::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

div[style*='overflow-y: auto']::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
