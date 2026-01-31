import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'requirements_qa_state'

// 从sessionStorage加载状态
const loadState = () => {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (stored) {
      return JSON.parse(stored)
    }
  } catch (e) {
    console.error('Failed to load state from sessionStorage:', e)
  }
  return null
}

// 保存状态到sessionStorage
const saveState = (state) => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (e) {
    console.error('Failed to save state to sessionStorage:', e)
  }
}

export const useRequirementsQAStore = defineStore('requirementsQA', () => {
  // Tab 1 - 需求文档问答状态
  const documentMode_qa = ref('single')
  const selectedGroupId_qa = ref(null)
  const selectedGroupIds_qa = ref([])
  const selectedProvider_qa = ref('local')
  const temperature_qa = ref(0.7)
  const useThinking_qa = ref(false)
  const crossEncoderMode_qa = ref('default')  // 'default', 'enhanced', 'smart'
  const messages = ref([])
  const inputMessage = ref('')
  const retrievalStatus = ref('正在检索知识图谱...')

  // Tab 2 - 需求文档生成状态
  const documentMode_similar = ref('single')
  const selectedGroupId_similar = ref(null)
  const selectedGroupIds_similar = ref([])
  const selectedProvider_similar = ref('local')
  const similarQuery = ref('')
  const similarDocuments = ref([])

  // Tab 3 - 需求分析状态
  const documentMode_analyze = ref('single')
  const selectedGroupId_analyze = ref(null)
  const selectedGroupIds_analyze = ref([])
  const selectedProvider_analyze = ref('qianwen')
  const analysisResult = ref(null)

  // 初始化：从sessionStorage加载状态
  const initialize = () => {
    const saved = loadState()
    if (saved) {
      // Tab 1
      if (saved.documentMode_qa !== undefined) documentMode_qa.value = saved.documentMode_qa
      if (saved.selectedGroupId_qa !== undefined) selectedGroupId_qa.value = saved.selectedGroupId_qa
      if (saved.selectedGroupIds_qa !== undefined) selectedGroupIds_qa.value = saved.selectedGroupIds_qa
      if (saved.selectedProvider_qa !== undefined) selectedProvider_qa.value = saved.selectedProvider_qa
      if (saved.temperature_qa !== undefined) temperature_qa.value = saved.temperature_qa
      if (saved.useThinking_qa !== undefined) useThinking_qa.value = saved.useThinking_qa
      if (saved.crossEncoderMode_qa !== undefined) crossEncoderMode_qa.value = saved.crossEncoderMode_qa
      if (saved.messages !== undefined) messages.value = saved.messages
      if (saved.inputMessage !== undefined) inputMessage.value = saved.inputMessage

      // Tab 2
      if (saved.documentMode_similar !== undefined) documentMode_similar.value = saved.documentMode_similar
      if (saved.selectedGroupId_similar !== undefined) selectedGroupId_similar.value = saved.selectedGroupId_similar
      if (saved.selectedGroupIds_similar !== undefined) selectedGroupIds_similar.value = saved.selectedGroupIds_similar
      if (saved.selectedProvider_similar !== undefined) selectedProvider_similar.value = saved.selectedProvider_similar
      if (saved.similarQuery !== undefined) similarQuery.value = saved.similarQuery
      if (saved.similarDocuments !== undefined) similarDocuments.value = saved.similarDocuments

      // Tab 3
      if (saved.documentMode_analyze !== undefined) documentMode_analyze.value = saved.documentMode_analyze
      if (saved.selectedGroupId_analyze !== undefined) selectedGroupId_analyze.value = saved.selectedGroupId_analyze
      if (saved.selectedGroupIds_analyze !== undefined) selectedGroupIds_analyze.value = saved.selectedGroupIds_analyze
      if (saved.selectedProvider_analyze !== undefined) selectedProvider_analyze.value = saved.selectedProvider_analyze
      if (saved.analysisResult !== undefined) analysisResult.value = saved.analysisResult
    }
  }

  // 保存状态到sessionStorage
  const persist = () => {
    const state = {
      // Tab 1
      documentMode_qa: documentMode_qa.value,
      selectedGroupId_qa: selectedGroupId_qa.value,
      selectedGroupIds_qa: selectedGroupIds_qa.value,
      selectedProvider_qa: selectedProvider_qa.value,
      temperature_qa: temperature_qa.value,
      useThinking_qa: useThinking_qa.value,
      crossEncoderMode_qa: crossEncoderMode_qa.value,
      messages: messages.value,
      inputMessage: inputMessage.value,

      // Tab 2
      documentMode_similar: documentMode_similar.value,
      selectedGroupId_similar: selectedGroupId_similar.value,
      selectedGroupIds_similar: selectedGroupIds_similar.value,
      selectedProvider_similar: selectedProvider_similar.value,
      similarQuery: similarQuery.value,
      similarDocuments: similarDocuments.value,

      // Tab 3
      documentMode_analyze: documentMode_analyze.value,
      selectedGroupId_analyze: selectedGroupId_analyze.value,
      selectedGroupIds_analyze: selectedGroupIds_analyze.value,
      selectedProvider_analyze: selectedProvider_analyze.value,
      analysisResult: analysisResult.value
    }
    saveState(state)
  }

  // 清除所有状态（包括对话历史）
  const clearAll = () => {
    // Tab 1 - 清除对话历史，保留配置
    messages.value = []
    inputMessage.value = ''

    // Tab 2 - 清除查询结果
    similarQuery.value = ''
    similarDocuments.value = []

    // Tab 3 - 清除分析结果
    analysisResult.value = null

    // 保存到sessionStorage
    persist()
  }

  // 清除Tab 1的对话历史
  const clearMessages = () => {
    messages.value = []
    inputMessage.value = ''
    persist()
  }

  // 监听状态变化，自动保存（延迟执行，避免初始化时触发）
  watch(
    [
      documentMode_qa, selectedGroupId_qa, selectedGroupIds_qa, selectedProvider_qa, temperature_qa, useThinking_qa, crossEncoderMode_qa,
      messages, inputMessage,
      documentMode_similar, selectedGroupId_similar, selectedGroupIds_similar, selectedProvider_similar,
      similarQuery, similarDocuments,
      documentMode_analyze, selectedGroupId_analyze, selectedGroupIds_analyze, selectedProvider_analyze,
      analysisResult
    ],
    () => {
      // 使用nextTick确保在初始化完成后再保存
      if (typeof window !== 'undefined') {
        setTimeout(() => {
          persist()
        }, 100)
      }
    },
    { deep: true }
  )

  // 初始化（只在浏览器环境中执行）
  if (typeof window !== 'undefined') {
    initialize()
  }

  return {
    // Tab 1
    documentMode_qa,
    selectedGroupId_qa,
    selectedGroupIds_qa,
    selectedProvider_qa,
    temperature_qa,
    useThinking_qa,
    crossEncoderMode_qa,
    messages,
    inputMessage,
    retrievalStatus,

    // Tab 2
    documentMode_similar,
    selectedGroupId_similar,
    selectedGroupIds_similar,
    selectedProvider_similar,
    similarQuery,
    similarDocuments,

    // Tab 3
    documentMode_analyze,
    selectedGroupId_analyze,
    selectedGroupIds_analyze,
    selectedProvider_analyze,
    analysisResult,

    // 方法
    clearAll,
    clearMessages,
    persist,
    initialize
  }
})

