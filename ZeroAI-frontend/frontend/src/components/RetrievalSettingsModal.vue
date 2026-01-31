<template>
  <a-modal
    v-model:open="visible"
    title="检索设置"
    width="600px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
      <!-- 检索方案选择 -->
      <a-form-item label="检索方案">
        <a-radio-group v-model:value="localSettings.scheme" @change="handleSchemeChange">
          <a-radio-button value="default">
            <a-space>
              <span>方案A</span>
              <a-tag color="blue" size="small">默认</a-tag>
            </a-space>
          </a-radio-button>
          <a-radio-button value="enhanced">
            <span>方案B</span>
          </a-radio-button>
          <a-radio-button value="smart">
            <span>方案C</span>
          </a-radio-button>
          <a-radio-button value="fast">
            <a-space>
              <span>方案D</span>
              <a-tag color="green" size="small">快速</a-tag>
            </a-space>
          </a-radio-button>
        </a-radio-group>
      </a-form-item>
      
      <!-- 方案描述 -->
      <a-form-item :wrapper-col="{ offset: 6, span: 18 }">
        <a-alert
          :message="schemeInfo.name"
          :description="schemeInfo.description"
          :type="schemeInfo.type"
          show-icon
        />
      </a-form-item>
      
      <!-- 通用参数 -->
      <a-divider orientation="left">通用参数</a-divider>
      
      <a-form-item label="检索数量">
        <a-slider
          v-model:value="localSettings.limit"
          :min="5"
          :max="50"
          :marks="{ 5: '5', 20: '20', 50: '50' }"
        />
        <span class="param-value">{{ localSettings.limit }} 条</span>
      </a-form-item>
      
      <a-form-item label="相似度阈值">
        <a-slider
          v-model:value="localSettings.simThreshold"
          :min="0"
          :max="100"
          :step="5"
          :marks="{ 0: '0%', 50: '50%', 100: '100%' }"
        />
        <span class="param-value">{{ localSettings.simThreshold }}%</span>
      </a-form-item>
      
      <a-form-item label="Thinking模式" v-if="supportThinking">
        <a-switch v-model:checked="localSettings.useThinking" />
        <span style="margin-left: 8px; color: #999">启用LLM深度思考</span>
      </a-form-item>
      
      <!-- 方案B特有参数 -->
      <template v-if="localSettings.scheme === 'enhanced'">
        <a-divider orientation="left">方案B参数</a-divider>
        <a-form-item label="截断长度">
          <a-slider
            v-model:value="localSettings.truncateLength"
            :min="100"
            :max="1000"
            :step="50"
            :marks="{ 100: '100', 500: '500', 1000: '1000' }"
          />
          <span class="param-value">{{ localSettings.truncateLength }} 字符</span>
        </a-form-item>
      </template>
      
      <!-- 方案C特有参数 -->
      <template v-if="localSettings.scheme === 'smart'">
        <a-divider orientation="left">方案C参数</a-divider>
        <a-form-item label="概括长度">
          <a-slider
            v-model:value="localSettings.summaryLength"
            :min="50"
            :max="500"
            :step="25"
            :marks="{ 50: '50', 200: '200', 500: '500' }"
          />
          <span class="param-value">{{ localSettings.summaryLength }} 字符</span>
        </a-form-item>
      </template>
      
      <!-- 方案D特有参数 -->
      <template v-if="localSettings.scheme === 'fast'">
        <a-divider orientation="left">方案D参数</a-divider>
        <a-form-item label="快速过滤阈值">
          <a-slider
            v-model:value="localSettings.fastThreshold"
            :min="0"
            :max="100"
            :step="5"
            :marks="{ 0: '0%', 50: '50%', 100: '100%' }"
          />
          <span class="param-value">{{ localSettings.fastThreshold }}%</span>
          <div style="color: #999; font-size: 12px; margin-top: 4px">
            低于此阈值的结果将被过滤（默认50%）
          </div>
        </a-form-item>
      </template>
      
      <!-- 预期效果 -->
      <a-divider orientation="left">预期效果</a-divider>
      <a-form-item :wrapper-col="{ offset: 6, span: 18 }">
        <a-descriptions :column="2" size="small" bordered>
          <a-descriptions-item label="响应时间">
            <a-tag :color="schemeInfo.speedColor">{{ schemeInfo.speed }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="准确度">
            <a-tag :color="schemeInfo.accuracyColor">{{ schemeInfo.accuracy }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>
      </a-form-item>
      
      <!-- 记住选择 -->
      <a-form-item :wrapper-col="{ offset: 6, span: 18 }">
        <a-checkbox v-model:checked="localSettings.remember">
          记住我的选择
        </a-checkbox>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  settings: {
    type: Object,
    default: () => ({})
  },
  supportThinking: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:open', 'confirm'])

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

// 本地设置副本
const localSettings = ref({
  scheme: 'default',
  limit: 20,
  simThreshold: 60,
  useThinking: false,
  truncateLength: 500,
  summaryLength: 200,
  fastThreshold: 50,
  remember: true
})

// 方案信息
const schemeInfoMap = {
  default: {
    name: '方案A（默认）- 均衡模式',
    description: '使用 Graphiti 默认交叉编码，性能好，响应快。适合大多数场景。',
    type: 'info',
    speed: '<1秒',
    speedColor: 'green',
    accuracy: '良好',
    accuracyColor: 'blue'
  },
  enhanced: {
    name: '方案B（增强）- 高准确率',
    description: '使用更丰富的字段进行匹配，准确率更高，但响应时间稍长。适合需要精确结果的场景。',
    type: 'warning',
    speed: '2-5秒',
    speedColor: 'orange',
    accuracy: '更好',
    accuracyColor: 'green'
  },
  smart: {
    name: '方案C（智能）- 智能增强',
    description: '使用 LLM 对检索结果进行概括和智能排序，准确率最高，但响应时间较长。适合复杂问题。',
    type: 'warning',
    speed: '5-15秒',
    speedColor: 'red',
    accuracy: '最好',
    accuracyColor: 'green'
  },
  fast: {
    name: '方案D（快速）- 极速模式',
    description: '不使用交叉编码，仅通过 RRF 预排序（向量+BM25融合），响应速度最快。适合对速度要求极高的场景。',
    type: 'success',
    speed: '<0.5秒',
    speedColor: 'green',
    accuracy: '一般',
    accuracyColor: 'orange'
  }
}

const schemeInfo = computed(() => schemeInfoMap[localSettings.value.scheme] || schemeInfoMap.default)

// 方案切换时调整默认参数
const handleSchemeChange = () => {
  const scheme = localSettings.value.scheme
  if (scheme === 'fast') {
    // 方案D使用较低的相似度阈值
    localSettings.value.simThreshold = 50
  } else {
    // 其他方案使用默认阈值
    localSettings.value.simThreshold = 60
  }
}

// 从localStorage加载保存的设置
const loadSavedSettings = () => {
  const saved = localStorage.getItem('retrievalSettings')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      Object.assign(localSettings.value, parsed)
    } catch (e) {
      console.error('加载保存的设置失败:', e)
    }
  }
}

// 保存设置到localStorage
const saveSettings = () => {
  if (localSettings.value.remember) {
    localStorage.setItem('retrievalSettings', JSON.stringify(localSettings.value))
  }
}

// 初始化时同步props.settings
watch(() => props.settings, (newVal) => {
  if (newVal && Object.keys(newVal).length > 0) {
    Object.assign(localSettings.value, newVal)
  }
}, { immediate: true, deep: true })

// 确认
const handleOk = () => {
  saveSettings()
  emit('confirm', { ...localSettings.value })
  visible.value = false
}

// 取消
const handleCancel = () => {
  visible.value = false
}

onMounted(() => {
  loadSavedSettings()
})
</script>

<style scoped>
.param-value {
  margin-left: 12px;
  color: #1890ff;
  font-weight: 500;
}
</style>

