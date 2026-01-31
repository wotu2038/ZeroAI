<template>
  <div class="smart-retrieval-results">
    <!-- 执行时间统计 -->
    <a-card title="执行统计" class="stats-card" size="small">
      <a-descriptions :column="3" bordered size="small">
        <a-descriptions-item label="阶段1耗时">
          <span class="time-value">{{ formatTime(result.execution_time?.stage1 || 0) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="阶段2耗时">
          <span class="time-value">{{ formatTime(result.execution_time?.stage2 || 0) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="总耗时">
          <span class="time-value total">{{ formatTime(result.execution_time?.total || 0) }}</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- 阶段1结果：文档召回 -->
    <a-card title="阶段1：Milvus快速召回（文档级别）" class="stage-card">
      <a-descriptions :column="1" bordered size="small" style="margin-bottom: 16px">
        <a-descriptions-item label="匹配文档总数">
          <span class="stat-value">{{ result.stage1?.total_documents || 0 }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="选择文档数">
          <span class="stat-value">{{ result.stage1?.top3_documents?.length || 0 }}</span>
        </a-descriptions-item>
      </a-descriptions>

      <a-list
        v-if="result.stage1?.top3_documents?.length > 0"
        :data-source="result.stage1.top3_documents"
        item-layout="vertical"
      >
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <a-tag color="blue">文档 {{ index + 1 }}</a-tag>
                  <span style="font-weight: 600">{{ item.document_name || item.group_id }}</span>
                  <a-tag color="orange">相似度: {{ (item.score * 100).toFixed(1) }}%</a-tag>
                </a-space>
              </template>
              <template #description>
                <a-descriptions :column="2" size="small" bordered>
                  <a-descriptions-item label="文档ID">
                    {{ item.group_id }}
                  </a-descriptions-item>
                  <a-descriptions-item label="最高分数">
                    {{ (item.max_score * 100).toFixed(1) }}%
                  </a-descriptions-item>
                  <a-descriptions-item label="平均分数">
                    {{ (item.avg_score * 100).toFixed(1) }}%
                  </a-descriptions-item>
                  <a-descriptions-item label="匹配向量数">
                    {{ item.vector_count }}
                  </a-descriptions-item>
                </a-descriptions>
                <div style="margin-top: 12px">
                  <a-space>
                    <a-tag v-if="item.matched_vectors?.section > 0" color="blue">
                      章节: {{ item.matched_vectors.section }}
                    </a-tag>
                    <a-tag v-if="item.matched_vectors?.document_summary > 0" color="cyan">
                      摘要: {{ item.matched_vectors.document_summary }}
                    </a-tag>
                    <a-tag v-if="item.matched_vectors?.image > 0" color="purple">
                      图片: {{ item.matched_vectors.image }}
                    </a-tag>
                    <a-tag v-if="item.matched_vectors?.table > 0" color="green">
                      表格: {{ item.matched_vectors.table }}
                    </a-tag>
                    <a-button 
                      type="link" 
                      size="small" 
                      @click="viewDocument(item)"
                      style="padding: 0"
                    >
                      查看文档
                    </a-button>
                  </a-space>
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-else description="没有找到匹配的文档" />
    </a-card>

    <!-- 阶段2结果：精细处理 -->
    <a-card 
      v-if="result.stage2" 
      title="阶段2：精细处理结果" 
      class="stage-card"
      style="margin-top: 24px"
    >
      <a-descriptions :column="1" bordered size="small" style="margin-bottom: 16px">
        <a-descriptions-item label="精筛结果总数">
          <span class="stat-value">{{ result.stage2?.total_count || 0 }}</span>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 嵌套Tab结构：Graphiti/Cognee -> Milvus/Neo4j -->
      <a-tabs v-model:activeKey="stage2ActiveTab" type="card" style="margin-top: 16px">
        <!-- Graphiti Tab -->
        <a-tab-pane key="graphiti" tab="Graphiti">
          <a-tabs v-model:activeKey="graphitiActiveTab" type="line" size="small">
            <a-tab-pane key="milvus" tab="Milvus">
              <RecallResultList 
                :results="getFilteredResults('graphiti', 'milvus')"
                source="smart_retrieval"
              />
            </a-tab-pane>
            <a-tab-pane key="neo4j" tab="Neo4j">
              <RecallResultList 
                :results="getFilteredResults('graphiti', 'neo4j')"
                source="smart_retrieval"
              />
            </a-tab-pane>
          </a-tabs>
        </a-tab-pane>

        <!-- Cognee Tab -->
        <a-tab-pane key="cognee" tab="Cognee">
          <a-tabs v-model:activeKey="cogneeActiveTab" type="line" size="small">
            <a-tab-pane key="milvus" tab="Milvus">
              <RecallResultList 
                :results="getFilteredResults('cognee', 'milvus')"
                source="smart_retrieval"
              />
            </a-tab-pane>
            <a-tab-pane key="neo4j" tab="Neo4j">
              <RecallResultList 
                :results="getFilteredResults('cognee', 'neo4j')"
                source="smart_retrieval"
              />
            </a-tab-pane>
          </a-tabs>
        </a-tab-pane>
      </a-tabs>

      <a-empty 
        v-if="!result.stage2?.refined_results?.length" 
        description="没有精筛结果" 
      />
    </a-card>

    <!-- 文档详情弹窗 -->
    <a-modal
      v-model:open="documentDetailVisible"
      :title="`查看文档详情 - ${documentDetailData?.group_id || documentDetailData?.document_id || ''}`"
      width="1000px"
      :footer="null"
      :maskClosable="true"
    >
      <a-spin :spinning="documentDetailLoading">
        <a-tabs v-model:activeKey="documentDetailTab" v-if="!documentDetailLoading">
          <!-- Tab 1: 原始文档 -->
          <a-tab-pane key="parsed" tab="原始文档">
            <div v-if="parsedContentText">
              <div 
                style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: 70vh; overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-wrap: break-word;"
                v-html="formatMarkdown(parsedContentText)"
              ></div>
            </div>
            <a-empty v-else description="原始文档不可用" />
          </a-tab-pane>
          
          <!-- Tab 2: 摘要文档 -->
          <a-tab-pane key="summary" tab="摘要文档">
            <div v-if="summaryContentText">
              <div 
                style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: 70vh; overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-wrap: break-word;"
                v-html="formatMarkdown(summaryContentText)"
              ></div>
            </div>
            <a-empty v-else description="摘要文档不可用" />
          </a-tab-pane>
          
          <!-- Tab 3: 结构化数据 -->
          <a-tab-pane key="structured" tab="结构化数据">
            <div v-if="structuredContentText">
              <pre 
                style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; max-height: 70vh; overflow: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;"
              >{{ structuredContentText }}</pre>
            </div>
            <a-empty v-else description="结构化数据不可用" />
          </a-tab-pane>
          
          <!-- Tab 4: 分块结果 -->
          <a-tab-pane key="chunks" tab="分块结果">
            <div v-if="chunksContentData">
              <!-- 分块统计信息 -->
              <a-descriptions title="分块信息" :column="4" bordered style="margin-bottom: 16px">
                <a-descriptions-item label="分块策略">
                  <a-tag color="blue">{{ getStrategyName(chunksContentData.strategy) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="总块数">
                  <a-tag color="green">{{ chunksContentData.total_chunks }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Max Tokens">
                  {{ chunksContentData.max_tokens }}
                </a-descriptions-item>
                <a-descriptions-item label="创建时间">
                  {{ chunksContentData.created_at ? new Date(chunksContentData.created_at).toLocaleString() : '-' }}
                </a-descriptions-item>
              </a-descriptions>
              
              <!-- 分块列表 -->
              <a-table
                :dataSource="chunksContentData.chunks || []"
                :columns="[
                  { title: '块ID', dataIndex: 'chunk_id', key: 'chunk_id', width: 100 },
                  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true }
                ]"
                :pagination="{ pageSize: 10 }"
                size="small"
                :scroll="{ y: 'calc(70vh - 200px)' }"
                rowKey="chunk_id"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'content'">
                    <a-tooltip :title="record.content">
                      <span style="max-width: 400px; display: inline-block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        {{ record.content?.substring(0, 100) }}{{ record.content?.length > 100 ? '...' : '' }}
                      </span>
                    </a-tooltip>
                  </template>
                </template>
              </a-table>
            </div>
            <a-empty v-else description="分块结果不可用（请先执行分块）" />
          </a-tab-pane>
        </a-tabs>
        <a-empty v-else description="正在加载文档详情..." />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, h } from 'vue'
import { message } from 'ant-design-vue'
import RecallResultList from './RecallResultList.vue'
import { getDocumentUploadList, getParsedContent, getSummaryContent, getStructuredContent, getChunks } from '../../api/documentUpload'

const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

// Tab状态管理
const stage2ActiveTab = ref('graphiti')
const graphitiActiveTab = ref('milvus')
const cogneeActiveTab = ref('milvus')

// 过滤结果：根据source和source_channel
const getFilteredResults = (source, sourceChannel) => {
  const allResults = props.result.stage2?.refined_results || []
  
  return allResults.filter(item => {
    const itemSource = item.source || ''
    const itemChannel = item.source_channel || ''
    
    // 匹配source和source_channel
    return itemSource === source && itemChannel === sourceChannel
  })
}

const formatTime = (seconds) => {
  if (seconds < 1) {
    return `${(seconds * 1000).toFixed(0)}ms`
  }
  return `${seconds.toFixed(2)}s`
}

// 文档详情相关
const documentDetailVisible = ref(false)
const documentDetailLoading = ref(false)
const documentDetailTab = ref('parsed')
const documentDetailData = ref(null)
const parsedContentText = ref('')
const summaryContentText = ref('')
const structuredContentText = ref('')
const chunksContentData = ref(null)

// 根据 group_id 查找 uploadId
const findUploadIdByGroupId = async (groupId) => {
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    const documents = response.documents || []
    // 查找匹配 group_id 的文档，优先选择最新的
    const matchedDocs = documents.filter(doc => doc.document_id === groupId)
    if (matchedDocs.length > 0) {
      // 按 id 降序排序，选择最新的
      matchedDocs.sort((a, b) => (b.id || 0) - (a.id || 0))
      return matchedDocs[0].id
    }
    return null
  } catch (error) {
    console.error('查找文档失败:', error)
    return null
  }
}

// 查看文档详情
const viewDocument = async (item) => {
  const groupId = item.group_id || item.document_id
  if (!groupId) {
    message.warning('该结果没有关联的文档')
    return
  }

  documentDetailVisible.value = true
  documentDetailData.value = item
  documentDetailTab.value = 'parsed'
  parsedContentText.value = ''
  summaryContentText.value = ''
  structuredContentText.value = ''
  chunksContentData.value = null
  documentDetailLoading.value = true

  try {
    // 根据 group_id 查找 uploadId
    const uploadId = await findUploadIdByGroupId(groupId)
    if (!uploadId) {
      throw new Error('未找到对应的文档，请确认文档已上传并处理')
    }

    // 并行加载三个内容
    const [parsedResponse, summaryResponse, structuredResponse] = await Promise.all([
      getParsedContent(uploadId),
      getSummaryContent(uploadId),
      getStructuredContent(uploadId)
    ])
    
    parsedContentText.value = parsedResponse.content || ''
    summaryContentText.value = summaryResponse.content || ''
    structuredContentText.value = structuredResponse.content 
      ? JSON.stringify(structuredResponse.content, null, 2)
      : ''
    
    // 单独加载 chunks（可能未分块，忽略错误）
    try {
      const chunksResponse = await getChunks(uploadId)
      chunksContentData.value = chunksResponse.content || null
    } catch (chunksError) {
      console.log('chunks 不可用（可能尚未分块）:', chunksError.message)
      chunksContentData.value = null
    }
  } catch (error) {
    console.error('加载文档详情失败:', error)
    message.error(`加载文档详情失败: ${error.message || '未知错误'}`)
    documentDetailVisible.value = false
  } finally {
    documentDetailLoading.value = false
  }
}

// 格式化 Markdown（简化版）
const formatMarkdown = (text) => {
  if (!text) return ''
  // 简单的 Markdown 格式化
  return text
    .replace(/\n/g, '<br>')
    .replace(/#{3}\s+(.+)/g, '<h3>$1</h3>')
    .replace(/#{2}\s+(.+)/g, '<h2>$1</h2>')
    .replace(/#{1}\s+(.+)/g, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
}

// 获取分块策略名称
const getStrategyName = (strategy) => {
  const strategyMap = {
    'level_1': '一级标题',
    'level_2': '二级标题',
    'fixed_token': '固定Token',
    'no_split': '不分块'
  }
  return strategyMap[strategy] || strategy
}
</script>

<style scoped>
.smart-retrieval-results {
  width: 100%;
}

.stats-card {
  margin-bottom: 24px;
}

.stage-card {
  margin-bottom: 24px;
}

.time-value {
  font-size: 14px;
  font-weight: 600;
  color: #1890ff;
}

.time-value.total {
  color: #52c41a;
  font-size: 16px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1890ff;
}
</style>

