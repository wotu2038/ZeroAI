<template>
  <a-card title="查询配置" class="config-card">
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
      <a-form-item label="查询文本">
        <a-textarea
          :value="queryText"
          @update:value="$emit('update:queryText', $event)"
          :rows="4"
          placeholder="输入你的查询问题..."
          :disabled="executing"
        />
      </a-form-item>

      <a-form-item label="检索范围">
        <a-radio-group 
          :value="searchMode" 
          @update:value="$emit('update:searchMode', $event)"
          :disabled="executing"
        >
          <a-radio value="all">全部文档</a-radio>
          <a-radio value="selected">指定文档</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item v-if="searchMode === 'selected'" label="选择文档">
        <a-select
          :value="selectedGroupIds"
          @update:value="$emit('update:selectedGroupIds', $event)"
          mode="multiple"
          placeholder="请选择要检索的文档"
          style="width: 100%"
          :loading="loadingDocuments"
          :disabled="loadingDocuments || executing"
          allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.document_id"
            :value="doc.document_id"
          >
            {{ doc.file_name }} ({{ doc.document_id }})
          </a-select-option>
        </a-select>
        <div style="margin-top: 8px">
          <a-button size="small" @click="$emit('load-documents')" :loading="loadingDocuments">
            刷新文档列表
          </a-button>
        </div>
      </a-form-item>

      <a-form-item label="返回数量">
        <a-input-number
          :value="topK"
          @update:value="$emit('update:topK', $event)"
          :min="5"
          :max="100"
          :step="5"
          :disabled="executing"
        />
        <span style="margin-left: 8px; color: #999">Top K</span>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
defineProps({
  queryText: {
    type: String,
    required: true
  },
  searchMode: {
    type: String,
    required: true
  },
  selectedGroupIds: {
    type: Array,
    required: true
  },
  topK: {
    type: Number,
    required: true
  },
  documents: {
    type: Array,
    default: () => []
  },
  loadingDocuments: {
    type: Boolean,
    default: false
  },
  executing: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:queryText', 'update:searchMode', 'update:selectedGroupIds', 'update:topK', 'load-documents'])
</script>

<style scoped>
.config-card {
  margin-bottom: 24px;
}
</style>

