<template>
  <a-card
    v-if="visible"
    :bordered="false"
    class="task-progress-card"
    :class="{ 'task-progress-card--minimized': minimized }"
  >
    <template #title>
      <a-space>
        <LoadingOutlined v-if="status === 'processing'" spin />
        <CheckCircleOutlined v-else-if="status === 'completed'" style="color: #52c41a" />
        <CloseCircleOutlined v-else-if="status === 'failed'" style="color: #ff4d4f" />
        <span>{{ title }}</span>
      </a-space>
    </template>
    
    <template #extra>
      <a-space>
        <a-button 
          type="text" 
          size="small" 
          @click="minimized = !minimized"
        >
          <template #icon>
            <UpOutlined v-if="!minimized" />
            <DownOutlined v-else />
          </template>
        </a-button>
        <a-button 
          type="text" 
          size="small" 
          @click="handleClose"
        >
          <template #icon><CloseOutlined /></template>
        </a-button>
      </a-space>
    </template>
    
    <div v-if="!minimized">
      <!-- 进度条 -->
      <a-progress
        :percent="progress"
        :status="progressStatus"
        :stroke-color="progressColor"
      />
      
      <!-- 当前步骤 -->
      <div class="task-step" v-if="currentStep">
        <a-tag :color="stepColor">步骤 {{ currentStep }}/{{ totalSteps }}</a-tag>
        <span class="task-message">{{ message }}</span>
      </div>
      
      <!-- 质量评估结果（如果有） -->
      <div v-if="qualityResult" class="quality-result">
        <a-divider style="margin: 12px 0">质量评估</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic
              title="分块质量"
              :value="qualityResult.chunking_score || 0"
              suffix="/ 100"
              :value-style="{ color: getScoreColor(qualityResult.chunking_score) }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="提取质量"
              :value="qualityResult.extraction_score || 0"
              suffix="/ 100"
              :value-style="{ color: getScoreColor(qualityResult.extraction_score) }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="图谱质量"
              :value="qualityResult.graph_score || 0"
              suffix="/ 100"
              :value-style="{ color: getScoreColor(qualityResult.graph_score) }"
            />
          </a-col>
        </a-row>
      </div>
      
      <!-- 错误信息（如果有） -->
      <a-alert
        v-if="status === 'failed' && error"
        :message="error.title || '处理失败'"
        :description="error.message || error"
        type="error"
        show-icon
        style="margin-top: 12px"
      >
        <template #action v-if="error.suggestion">
          <div style="font-size: 12px; color: #666">
            💡 {{ error.suggestion }}
          </div>
        </template>
      </a-alert>
      
      <!-- 完成操作按钮 -->
      <div v-if="status === 'completed'" class="task-actions">
        <a-space>
          <a-button type="primary" size="small" @click="$emit('view-result')">
            查看结果
          </a-button>
          <a-button size="small" @click="handleClose">
            关闭
          </a-button>
        </a-space>
      </div>
    </div>
  </a-card>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloseOutlined,
  UpOutlined,
  DownOutlined
} from '@ant-design/icons-vue'
import { connectToTask } from '@/utils/websocket'

const props = defineProps({
  taskId: {
    type: String,
    required: true
  },
  title: {
    type: String,
    default: '文档处理中'
  },
  autoConnect: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['close', 'complete', 'error', 'view-result'])

// 状态
const visible = ref(true)
const minimized = ref(false)
const status = ref('processing') // processing, completed, failed
const progress = ref(0)
const message = ref('')
const currentStep = ref(0)
const totalSteps = ref(0)
const qualityResult = ref(null)
const error = ref(null)

// WebSocket 连接
let ws = null

// 计算属性
const progressStatus = computed(() => {
  if (status.value === 'completed') return 'success'
  if (status.value === 'failed') return 'exception'
  return 'active'
})

const progressColor = computed(() => {
  if (status.value === 'completed') return '#52c41a'
  if (status.value === 'failed') return '#ff4d4f'
  return '#1890ff'
})

const stepColor = computed(() => {
  if (status.value === 'completed') return 'success'
  if (status.value === 'failed') return 'error'
  return 'processing'
})

// 方法
const getScoreColor = (score) => {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#ff4d4f'
}

const handleClose = () => {
  visible.value = false
  if (ws) {
    ws.disconnect()
  }
  emit('close')
}

const connectWebSocket = () => {
  if (!props.taskId) return

  ws = connectToTask(props.taskId, {
    onProgress: (data) => {
      progress.value = data.progress || 0
      message.value = data.message || ''
      
      // 解析步骤信息
      if (data.step && data.total_steps) {
        currentStep.value = data.step
        totalSteps.value = data.total_steps
      }
      
      // 质量评估结果
      if (data.quality) {
        qualityResult.value = data.quality
      }
    },
    onComplete: (data) => {
      status.value = 'completed'
      progress.value = 100
      message.value = data.message || '处理完成'
      
      if (data.result?.quality) {
        qualityResult.value = data.result.quality
      }
      
      emit('complete', data)
    },
    onError: (data) => {
      status.value = 'failed'
      error.value = data.error || data.message || '处理失败'
      emit('error', data)
    }
  })
}

// 生命周期
onMounted(() => {
  if (props.autoConnect) {
    connectWebSocket()
  }
})

onUnmounted(() => {
  if (ws) {
    ws.disconnect()
  }
})

// 监听 taskId 变化
watch(() => props.taskId, (newVal) => {
  if (newVal && props.autoConnect) {
    // 重置状态
    status.value = 'processing'
    progress.value = 0
    message.value = ''
    error.value = null
    qualityResult.value = null
    
    // 重新连接
    if (ws) {
      ws.disconnect()
    }
    connectWebSocket()
  }
})

// 暴露方法
defineExpose({
  connect: connectWebSocket,
  disconnect: () => ws?.disconnect()
})
</script>

<style scoped>
.task-progress-card {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 400px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  transition: all 0.3s;
}

.task-progress-card--minimized {
  width: 300px;
}

.task-step {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-message {
  color: #666;
  font-size: 13px;
}

.quality-result {
  margin-top: 12px;
}

.task-actions {
  margin-top: 16px;
  text-align: right;
}
</style>

