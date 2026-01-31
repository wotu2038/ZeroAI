<template>
  <div>
    <!-- 配置区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item label="选择文档">
        <a-select
          v-model:value="selectedDocumentId"
          placeholder="请选择已处理的文档"
          style="width: 100%"
          :loading="loadingDocuments"
          :disabled="loadingDocuments || executing"
          @change="handleDocumentChange"
          allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.id"
            :value="doc.id"
          >
            {{ doc.file_name }} (ID: {{ doc.id }})
          </a-select-option>
        </a-select>
      </a-form-item>
    </a-form>

    <!-- 执行区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item>
        <a-space>
          <a-button 
            type="primary" 
            @click="handleExecute" 
            :loading="executing"
            :disabled="!selectedDocumentId || executing"
          >
            <template #icon><PlayCircleOutlined /></template>
            执行Milvus向量化处理
          </a-button>
          <a-button @click="handleClear" :disabled="executing">
            清空结果
          </a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 结果区域 -->
    <div v-if="executing" style="text-align: center; padding: 40px">
      <a-spin size="large">
        <template #indicator>
          <LoadingOutlined style="font-size: 24px" spin />
        </template>
      </a-spin>
      <div style="margin-top: 12px; color: #999">
        {{ executionStatus }}
      </div>
    </div>

    <div v-else-if="executionResult">
      <a-card title="向量化处理结果" style="margin-bottom: 24px">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="文档摘要向量">
            {{ executionResult.summary_vector_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="Requirement向量">
            {{ executionResult.requirement_vector_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="流程/规则向量">
            {{ executionResult.rule_vector_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="章节向量">
            {{ executionResult.chunk_vector_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="图片向量">
            <a-tag color="blue">{{ executionResult.image_vector_count || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="表格向量">
            <a-tag color="green">{{ executionResult.table_vector_count || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="总向量数" :span="2">
            <a-typography-text strong style="font-size: 16px; color: #1890ff">
            {{ executionResult.total_vector_count || 0 }}
            </a-typography-text>
          </a-descriptions-item>
          <a-descriptions-item label="执行状态" :span="2">
            <a-tag color="green" v-if="executionResult.success">成功</a-tag>
            <a-tag color="red" v-else>失败</a-tag>
          </a-descriptions-item>
        </a-descriptions>
        
        <!-- 详细信息展示 -->
        <a-divider />
        <a-row :gutter="16" style="margin-top: 16px">
          <a-col :span="12">
            <a-statistic
              title="文本向量"
              :value="(executionResult.summary_vector_count || 0) + 
                      (executionResult.requirement_vector_count || 0) + 
                      (executionResult.rule_vector_count || 0) + 
                      (executionResult.chunk_vector_count || 0)"
              :value-style="{ color: '#1890ff' }"
            />
          </a-col>
          <a-col :span="12">
            <a-statistic
              title="多媒体向量"
              :value="(executionResult.image_vector_count || 0) + 
                      (executionResult.table_vector_count || 0)"
              :value-style="{ color: '#52c41a' }"
            />
          </a-col>
        </a-row>
        
        <!-- 图片和表格处理提示 -->
        <a-alert
          v-if="(executionResult.image_vector_count || 0) > 0 || (executionResult.table_vector_count || 0) > 0"
          message="图片和表格向量化说明"
          type="info"
          style="margin-top: 16px"
          show-icon
        >
          <template #description>
            <div>
              <p v-if="executionResult.image_vector_count > 0">
                • 已处理 <strong>{{ executionResult.image_vector_count }}</strong> 张图片（使用 OCR 提取文字后向量化）
              </p>
              <p v-if="executionResult.table_vector_count > 0">
                • 已处理 <strong>{{ executionResult.table_vector_count }}</strong> 个表格（转换为结构化文本后向量化）
              </p>
              <p style="margin-top: 8px; color: #666; font-size: 12px">
                提示：图片和表格向量已参与检索，可在"Milvus快速召回"标签页中查询
              </p>
            </div>
          </template>
        </a-alert>
      </a-card>
    </div>

    <!-- 空状态 -->
    <a-empty
      v-else
      description="请选择文档并点击执行按钮开始处理"
      style="margin: 60px 0"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { getDocumentUploadList } from '../../api/documentUpload'
import { step3MilvusVectorize } from '../../api/intelligentChat'

const documents = ref([])
const loadingDocuments = ref(false)
const selectedDocumentId = ref(null)
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    if (response && response.documents) {
      documents.value = response.documents.filter(doc => doc.document_id)
    } else {
      documents.value = []
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
    documents.value = []
  } finally {
    loadingDocuments.value = false
  }
}

const handleDocumentChange = () => {
  executionResult.value = null
}

const handleExecute = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  const selectedDoc = documents.value.find(d => d.id === selectedDocumentId.value)
  if (!selectedDoc || !selectedDoc.document_id) {
    message.warning('该文档尚未完成Graphiti处理，请先完成Tab 1')
    return
  }

  executing.value = true
  executionStatus.value = '正在执行Milvus向量化处理...'
  executionResult.value = null

  try {
    const result = await step3MilvusVectorize({
      upload_id: selectedDocumentId.value,
      group_id: selectedDoc.document_id
    })

    executionResult.value = result
    message.success('Milvus向量化处理完成')
  } catch (error) {
    console.error('执行失败:', error)
    message.error(`执行失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    executing.value = false
    executionStatus.value = ''
  }
}

const handleClear = () => {
  executionResult.value = null
  message.success('结果已清空')
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
</style>

