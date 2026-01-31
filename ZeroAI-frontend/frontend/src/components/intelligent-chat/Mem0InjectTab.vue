<template>
  <div style="height: calc(100vh - 200px); display: flex; flex-direction: column">
    <!-- 标题和会话管理 -->
    <div style="padding: 16px; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center">
      <div>
        <h3 style="margin: 0">Mem0 上下文管理验证 - 独立问答</h3>
        <div style="font-size: 12px; color: #999; margin-top: 4px">
          会话ID: {{ sessionId || '未设置' }} | 用户ID: {{ userId || '未设置' }}
        </div>
      </div>
      <a-space>
        <a-button size="small" @click="handleNewSession">新建会话</a-button>
        <a-button size="small" @click="handleClearHistory" :disabled="conversationHistory.length === 0">清空历史</a-button>
      </a-space>
    </div>

    <!-- 主内容区域 -->
    <div style="flex: 1; display: flex; overflow: hidden">
      <!-- 左侧：对话历史 -->
      <div style="flex: 1; display: flex; flex-direction: column; border-right: 1px solid #f0f0f0; overflow: hidden">
        <div style="padding: 16px; border-bottom: 1px solid #f0f0f0; background: #fafafa">
          <strong>对话历史</strong>
          <span style="margin-left: 8px; color: #999; font-size: 12px">({{ conversationHistory.length }} 轮)</span>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: 16px" ref="chatContainer">
          <a-empty v-if="conversationHistory.length === 0" description="开始对话吧！" style="margin-top: 100px" />
          <div v-else>
            <div
              v-for="(msg, index) in conversationHistory"
              :key="index"
              :style="{
                marginBottom: '16px',
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
              }"
            >
              <div
                :style="{
                  maxWidth: '70%',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  background: msg.role === 'user' ? '#1890ff' : '#f0f0f0',
                  color: msg.role === 'user' ? '#fff' : '#333'
                }"
              >
                <div style="font-size: 12px; opacity: 0.8; marginBottom: '4px'">
                  {{ msg.role === 'user' ? '用户' : '助手' }}
                </div>
                <div style="whiteSpace: 'pre-wrap'">{{ msg.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：Mem0 记忆信息 -->
      <div style="width: 400px; display: flex; flex-direction: column; overflow: hidden; background: #fafafa">
        <div style="padding: 16px; border-bottom: 1px solid #f0f0f0">
          <strong>Mem0 记忆信息</strong>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: 16px">
          <!-- 记忆统计 -->
          <a-card size="small" style="margin-bottom: 16px" title="记忆统计">
            <a-descriptions :column="1" size="small">
              <a-descriptions-item label="检索到记忆">
                {{ currentMemories.length }} 条
              </a-descriptions-item>
              <a-descriptions-item label="对话轮数">
                {{ conversationHistory.length / 2 }} 轮
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 检索到的记忆 -->
          <a-card size="small" title="检索到的记忆" v-if="currentMemories.length > 0">
            <a-list
              :data-source="currentMemories"
              :pagination="false"
              size="small"
            >
              <template #renderItem="{ item, index }">
                <a-list-item style="padding: 8px 0">
                  <a-list-item-meta>
                    <template #title>
                      <div style="font-size: 12px; color: #999">记忆 {{ index + 1 }}</div>
                    </template>
                    <template #description>
                      <div style="font-size: 13px; margin-top: 4px">{{ item.memory || item.content || '无内容' }}</div>
                      <div v-if="item.score !== undefined" style="font-size: 11px; color: #1890ff; margin-top: 4px">
                        相关性: {{ (item.score * 100).toFixed(1) }}%
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>

          <a-empty v-else description="暂无记忆" style="margin-top: 40px" />
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div style="padding: 16px; border-top: 1px solid #f0f0f0; background: #fff">
      <a-form layout="inline" style="width: 100%">
        <a-form-item style="flex: 1; margin: 0">
          <a-input
            v-model:value="inputQuery"
            placeholder="输入您的问题..."
            @pressEnter="handleSend"
            :disabled="sending"
            size="large"
          />
        </a-form-item>
        <a-form-item style="margin: 0">
          <a-space>
            <a-button
              type="primary"
              @click="handleSend"
              :loading="sending"
              :disabled="!inputQuery.trim() || sending"
              size="large"
            >
              发送
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
      <div style="margin-top: 8px; font-size: 12px; color: #999">
        <a-space>
          <span>会话ID:</span>
          <a-input
            v-model:value="sessionId"
            placeholder="可选，用于会话级上下文"
            size="small"
            style="width: 200px"
          />
          <span>用户ID:</span>
          <a-input
            v-model:value="userId"
            placeholder="可选，未登录时使用"
            size="small"
            style="width: 200px"
          />
        </a-space>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { message } from 'ant-design-vue'
import { mem0Chat } from '../../api/intelligentChat'

const inputQuery = ref('')
const sessionId = ref('')
const userId = ref('')
const sending = ref(false)
const conversationHistory = ref([])
const currentMemories = ref([])
const chatContainer = ref(null)

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// 监听对话历史变化，自动滚动
watch(conversationHistory, () => {
  scrollToBottom()
}, { deep: true })

const handleSend = async () => {
  if (!inputQuery.value.trim()) {
    message.warning('请输入问题')
    return
  }

  const query = inputQuery.value.trim()
  inputQuery.value = ''

  // 添加用户消息到历史
  conversationHistory.value.push({
    role: 'user',
    content: query
  })

  sending.value = true

  try {
    const result = await mem0Chat({
      query: query,
      user_id: userId.value || undefined,
      session_id: sessionId.value || undefined,
      conversation_history: conversationHistory.value.slice(0, -1), // 不包含刚添加的用户消息
      provider: 'local',
      temperature: 0.7
    })

    // 更新对话历史
    conversationHistory.value = result.conversation_history || conversationHistory.value

    // 更新记忆信息
    currentMemories.value = result.memories || []

    message.success('回答生成成功')
  } catch (error) {
    console.error('发送失败:', error)
    message.error(`发送失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
    
    // 移除刚才添加的用户消息（因为失败了）
    if (conversationHistory.value.length > 0 && conversationHistory.value[conversationHistory.value.length - 1].role === 'user') {
      conversationHistory.value.pop()
    }
  } finally {
    sending.value = false
  }
}

const handleNewSession = () => {
  sessionId.value = `session_${Date.now()}`
  conversationHistory.value = []
  currentMemories.value = []
  message.success('已创建新会话')
}

const handleClearHistory = () => {
  conversationHistory.value = []
  currentMemories.value = []
  message.success('已清空对话历史')
}
</script>

<style scoped>
/* 确保滚动条样式 */
:deep(.ant-list-item) {
  border-bottom: none !important;
}
</style>
