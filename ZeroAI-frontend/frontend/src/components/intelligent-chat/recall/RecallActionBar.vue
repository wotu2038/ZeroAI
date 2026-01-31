<template>
  <a-card class="action-bar-card">
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
      <a-form-item>
        <a-space>
          <a-button 
            type="primary" 
            size="large"
            @click="$emit('execute')"
            :disabled="!hasQuery || executing"
          >
            <template #icon><SearchOutlined /></template>
            执行Milvus快速召回
          </a-button>
          <a-button size="large" @click="$emit('clear')" :disabled="executing">
            <template #icon><ClearOutlined /></template>
            清空结果
          </a-button>
        </a-space>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
import { SearchOutlined, ClearOutlined } from '@ant-design/icons-vue'

defineProps({
  executing: {
    type: Boolean,
    default: false
  },
  hasQuery: {
    type: Boolean,
    default: false
  }
})

defineEmits(['execute', 'clear'])
</script>

<style scoped>
.action-bar-card {
  margin-bottom: 24px;
}
</style>

