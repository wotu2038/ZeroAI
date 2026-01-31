<template>
  <div class="smart-retrieval-tab">
    <!-- 配置区域 -->
    <RecallConfigForm
      v-model:query-text="queryText"
      v-model:search-mode="searchMode"
      v-model:selected-group-ids="selectedGroupIds"
      v-model:top-k="topK"
      :documents="documents"
      :loading-documents="loadingDocuments"
      :executing="executing"
      @load-documents="loadDocuments"
    />

    <!-- 高级配置 -->
    <a-card title="高级配置" class="config-card" size="small">
      <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="选择Top3文档">
          <a-switch
            :checked="top3"
            @update:checked="top3 = $event"
            :disabled="executing"
          />
          <span style="margin-left: 8px; color: #666">从Top50中选择Top3文档进行精细处理</span>
        </a-form-item>
        <a-form-item label="启用精细处理">
          <a-switch
            :checked="enableRefine"
            @update:checked="enableRefine = $event"
            :disabled="executing"
          />
          <span style="margin-left: 8px; color: #666">阶段2：使用Graphiti和Cognee进行精细处理</span>
        </a-form-item>
        <a-form-item label="启用图遍历">
          <a-switch
            :checked="enableGraphTraverse"
            @update:checked="enableGraphTraverse = $event"
            :disabled="executing"
          />
          <span style="margin-left: 8px; color: #666">使用Neo4j图遍历扩展相关实体</span>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 操作区域 -->
    <RecallActionBar
      :executing="executing"
      :has-query="!!queryText.trim()"
      @execute="handleExecute"
      @clear="handleClear"
    />

    <!-- 加载状态 -->
    <LoadingState
      v-if="executing"
      :status="executionStatus"
      :progress="executionProgress"
      :steps="executionSteps"
      :current-step-index="currentStepIndex"
      :elapsed-time="elapsedTime"
    />

    <!-- 结果区域 -->
    <SmartRetrievalResults
      v-else-if="executionResult"
      :result="executionResult"
    />

    <!-- 空状态 -->
    <EmptyState v-else />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { getDocumentUploadList } from '../../api/documentUpload'
import { smartRetrieval } from '../../api/intelligentChat'
import RecallConfigForm from './recall/RecallConfigForm.vue'
import RecallActionBar from './recall/RecallActionBar.vue'
import SmartRetrievalResults from './SmartRetrievalResults.vue'
import LoadingState from './recall/LoadingState.vue'
import EmptyState from './recall/EmptyState.vue'

const documents = ref([])
const loadingDocuments = ref(false)
const queryText = ref('')
const searchMode = ref('all')
const selectedGroupIds = ref([])
const topK = ref(50)
const top3 = ref(true)
const enableRefine = ref(true)
const enableGraphTraverse = ref(true)
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)
const executionProgress = ref(0)
const executionSteps = ref([])
const currentStepIndex = ref(0)
const elapsedTime = ref('')
let elapsedInterval = null
let progressInterval = null

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, 'completed')
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

const updateElapsedTime = () => {
  if (!executing.value) return
  const elapsed = Math.floor((Date.now() - startTime) / 1000)
  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60
  elapsedTime.value = `${minutes}分${seconds}秒`
}

const updateProgress = () => {
  if (!executing.value) return
  
  const elapsed = (Date.now() - startTime) / 1000 // 已用时间（秒）
  
  // 根据时间估算进度（阶段1约30%，阶段2约70%）
  if (elapsed < 2) {
    // 阶段1：生成查询向量
    currentStepIndex.value = 0
    executionProgress.value = Math.min(10, (elapsed / 2) * 10)
    executionStatus.value = '正在生成查询向量...'
  } else if (elapsed < 5) {
    // 阶段1：Milvus向量搜索
    currentStepIndex.value = 1
    executionProgress.value = Math.min(30, 10 + ((elapsed - 2) / 3) * 20)
    executionStatus.value = '阶段1：Milvus向量搜索中...'
    if (executionSteps.value[1]) {
      executionSteps.value[1].status = 'processing'
    }
  } else if (elapsed < 7) {
    // 阶段1：聚合结果并选择Top3文档
    currentStepIndex.value = 2
    executionProgress.value = Math.min(35, 30 + ((elapsed - 5) / 2) * 5)
    executionStatus.value = '阶段1：聚合结果并选择Top3文档...'
    if (executionSteps.value[1]) {
      executionSteps.value[1].status = 'finish'
      executionSteps.value[1].time = (5 - 2).toFixed(1)
    }
    if (executionSteps.value[2]) {
      executionSteps.value[2].status = 'processing'
    }
  } else if (elapsed < 10) {
    // 阶段2开始：Graphiti搜索
    currentStepIndex.value = 3
    executionProgress.value = Math.min(50, 35 + ((elapsed - 7) / 3) * 15)
    executionStatus.value = '阶段2：使用Graphiti进行语义搜索...'
    if (executionSteps.value[2]) {
      executionSteps.value[2].status = 'finish'
      executionSteps.value[2].time = (7 - 5).toFixed(1)
    }
    if (executionSteps.value[3]) {
      executionSteps.value[3].status = 'processing'
    }
  } else if (elapsed < 15) {
    // 阶段2：Cognee搜索
    currentStepIndex.value = 4
    executionProgress.value = Math.min(70, 50 + ((elapsed - 10) / 5) * 20)
    executionStatus.value = '阶段2：使用Cognee进行语义搜索...'
    if (executionSteps.value[3]) {
      executionSteps.value[3].status = 'finish'
      executionSteps.value[3].time = (10 - 7).toFixed(1)
    }
    if (executionSteps.value[4]) {
      executionSteps.value[4].status = 'processing'
    }
  } else if (elapsed < 20) {
    // 阶段2：Milvus深度检索
    currentStepIndex.value = 5
    executionProgress.value = Math.min(85, 70 + ((elapsed - 15) / 5) * 15)
    executionStatus.value = '阶段2：Milvus深度向量检索中...'
    if (executionSteps.value[4]) {
      executionSteps.value[4].status = 'finish'
      executionSteps.value[4].time = (15 - 10).toFixed(1)
    }
    if (executionSteps.value[5]) {
      executionSteps.value[5].status = 'processing'
    }
  } else {
    // 阶段2：Neo4j图遍历和结果合并
    currentStepIndex.value = enableGraphTraverse.value ? 6 : 7
    executionProgress.value = Math.min(95, 85 + ((elapsed - 20) / 5) * 10)
    executionStatus.value = enableGraphTraverse.value 
      ? '阶段2：Neo4j图遍历扩展相关实体...'
      : '阶段2：合并结果并排序...'
    if (executionSteps.value[5]) {
      executionSteps.value[5].status = 'finish'
      executionSteps.value[5].time = (20 - 15).toFixed(1)
    }
    if (executionSteps.value[6] && enableGraphTraverse.value) {
      executionSteps.value[6].status = 'processing'
    }
  }
}

let startTime = null

const handleExecute = async () => {
  if (!queryText.value.trim()) {
    message.warning('请输入查询文本')
    return
  }

  if (searchMode.value === 'selected' && (!selectedGroupIds.value || selectedGroupIds.value.length === 0)) {
    message.warning('请选择要检索的文档')
    return
  }

  executing.value = true
  executionStatus.value = '正在初始化...'
  executionResult.value = null
  executionProgress.value = 0
  currentStepIndex.value = 0
  elapsedTime.value = '0分0秒'
  startTime = Date.now()

  // 初始化步骤列表
  executionSteps.value = [
    { title: '生成查询向量', status: 'wait', message: '正在将查询文本转换为向量...', time: null },
    { title: 'Milvus向量搜索', status: 'wait', message: '在Milvus中搜索相关文档向量...', time: null },
    { title: '聚合结果并选择Top3文档', status: 'wait', message: '按文档聚合结果并选择Top3文档...', time: null },
    { title: 'Graphiti语义搜索', status: 'wait', message: '使用Graphiti知识图谱进行语义搜索...', time: null },
    { title: 'Cognee语义搜索', status: 'wait', message: '使用Cognee知识图谱进行语义搜索...', time: null },
    { title: 'Milvus深度检索', status: 'wait', message: '对所有向量类型进行深度检索...', time: null }
  ]

  if (enableGraphTraverse.value) {
    executionSteps.value.push({
      title: 'Neo4j图遍历扩展',
      status: 'wait',
      message: '使用Neo4j图遍历扩展相关实体...',
      time: null
    })
  }

  executionSteps.value.push({
    title: '合并结果并排序',
    status: 'wait',
    message: '去重、合并并排序最终结果...',
    time: null
  })

  // 启动进度更新
  elapsedInterval = setInterval(updateElapsedTime, 1000)
  progressInterval = setInterval(updateProgress, 500)

  try {
    const params = {
      query: queryText.value,
      top_k: topK.value,
      top3: top3.value,
      enable_refine: enableRefine.value,
      enable_bm25: true,
      enable_graph_traverse: enableGraphTraverse.value
    }

    if (searchMode.value === 'selected') {
      params.group_ids = selectedGroupIds.value
    }

    // 执行查询
    const result = await smartRetrieval(params)
    
    // 完成所有步骤
    executionProgress.value = 100
    currentStepIndex.value = executionSteps.value.length
    executionSteps.value.forEach(step => {
      if (step.status === 'processing') {
        step.status = 'finish'
      }
      if (step.status === 'wait') {
        step.status = 'finish'
      }
    })
    
    executionResult.value = result
    executionStatus.value = '检索完成！'
    
    const stage1Count = result.stage1?.top3_documents?.length || 0
    const stage2Count = result.stage2?.total_count || 0
    message.success(`智能检索完成！阶段1找到 ${stage1Count} 个文档，阶段2精筛得到 ${stage2Count} 个结果`)
  } catch (error) {
    console.error('执行失败:', error)
    message.error(`执行失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
    // 标记失败的步骤
    if (executionSteps.value[currentStepIndex.value]) {
      executionSteps.value[currentStepIndex.value].status = 'error'
    }
  } finally {
    executing.value = false
    executionStatus.value = ''
    if (elapsedInterval) {
      clearInterval(elapsedInterval)
      elapsedInterval = null
    }
    if (progressInterval) {
      clearInterval(progressInterval)
      progressInterval = null
    }
  }
}

const handleClear = () => {
  executionResult.value = null
  queryText.value = ''
  message.success('结果已清空')
}

onMounted(() => {
  loadDocuments()
})

onUnmounted(() => {
  if (elapsedInterval) {
    clearInterval(elapsedInterval)
  }
  if (progressInterval) {
    clearInterval(progressInterval)
  }
})
</script>

<style scoped>
.smart-retrieval-tab {
  padding: 0;
}

.config-card {
  margin-bottom: 24px;
}
</style>

