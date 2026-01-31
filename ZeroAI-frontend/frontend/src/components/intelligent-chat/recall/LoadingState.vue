<template>
  <div class="loading-state">
    <a-card title="检索进度" :bordered="false" class="progress-card">
      <a-spin :spinning="true" size="large">
        <div class="progress-content">
          <!-- 当前状态 -->
          <div class="current-status">
            <LoadingOutlined style="font-size: 20px; color: #1890ff; margin-right: 8px" spin />
            <span class="status-text">{{ currentStatus }}</span>
          </div>

          <!-- 进度条 -->
          <a-progress
            :percent="progress"
            :status="progressStatus"
            :stroke-color="progressColor"
            :show-info="true"
            style="margin: 20px 0"
          />

          <!-- 步骤列表 -->
          <div class="steps-container" v-if="steps && steps.length > 0">
            <a-steps :current="currentStepIndex" direction="vertical" size="small">
              <a-step
                v-for="(step, index) in steps"
                :key="index"
                :title="step.title"
                :status="getStepStatus(index)"
              >
                <template #description>
                  <div class="step-description">
                    <span v-if="step.message">{{ step.message }}</span>
                    <span v-if="step.count" class="step-count">（{{ step.count }}）</span>
                    <span v-if="step.time" class="step-time">耗时: {{ step.time }}秒</span>
                  </div>
                </template>
              </a-step>
            </a-steps>
          </div>

          <!-- 已用时间 -->
          <div class="elapsed-time" v-if="elapsedTime">
            <ClockCircleOutlined style="margin-right: 4px" />
            已用时间: {{ elapsedTime }}
          </div>
        </div>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  status: {
    type: String,
    default: '正在处理...'
  },
  progress: {
    type: Number,
    default: 0
  },
  steps: {
    type: Array,
    default: () => []
  },
  currentStepIndex: {
    type: Number,
    default: 0
  },
  elapsedTime: {
    type: String,
    default: ''
  }
})

const currentStatus = computed(() => {
  if (props.status) return props.status
  if (props.steps && props.steps.length > 0 && props.currentStepIndex < props.steps.length) {
    return props.steps[props.currentStepIndex].title
  }
  return '正在处理...'
})

const progressStatus = computed(() => {
  if (props.progress >= 100) return 'success'
  return 'active'
})

const progressColor = computed(() => {
  if (props.progress >= 100) return '#52c41a'
  return '#1890ff'
})

const getStepStatus = (index) => {
  if (index < props.currentStepIndex) return 'finish'
  if (index === props.currentStepIndex) return 'process'
  return 'wait'
}
</script>

<style scoped>
.loading-state {
  padding: 20px 0;
}

.progress-card {
  margin-bottom: 24px;
}

.progress-content {
  padding: 20px;
}

.current-status {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.status-text {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.steps-container {
  margin-top: 24px;
  max-height: 400px;
  overflow-y: auto;
}

.step-description {
  color: #666;
  font-size: 13px;
  margin-top: 4px;
}

.step-count {
  color: #1890ff;
  font-weight: 500;
}

.step-time {
  color: #999;
  margin-left: 8px;
}

.elapsed-time {
  margin-top: 16px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
</style>

