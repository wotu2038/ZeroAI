<template>
  <div class="recall-result-list">
    <a-empty 
      v-if="!results || results.length === 0"
      description="暂无结果"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
      class="empty-result"
    />
    <a-list
      v-else
      :data-source="results"
      :pagination="{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }"
      class="result-list"
    >
      <template #renderItem="{ item, index }">
        <a-list-item class="result-item">
          <a-list-item-meta>
            <template #title>
              <div class="result-header">
                <a-space wrap>
                  <a-tag :color="getSourceColor(source)" class="source-tag">
                    {{ getSourceLabel(source) }}
                  </a-tag>
                  <a-tag :color="getTypeColor(item.type)" class="type-tag">
                    {{ getTypeLabel(item.type) }}
                  </a-tag>
                  <span class="result-name">{{ item.name || item.content?.substring(0, 50) || `结果 ${index + 1}` }}</span>
                  <a-tag color="orange" class="score-tag">
                    相似度: {{ (item.score * 100).toFixed(1) }}%
                  </a-tag>
                </a-space>
              </div>
            </template>
            <template #description>
              <div class="result-content">
                <!-- 图片类型特殊展示 -->
                <div v-if="item.type === 'image' && item.metadata?.image_path" class="image-result">
                  <a-alert
                    message="图片结果"
                    type="info"
                    show-icon
                    style="margin-bottom: 8px"
                  >
                    <template #description>
                      <div>
                        <p><strong>图片路径:</strong> {{ item.metadata.image_path }}</p>
                        <p v-if="item.metadata.description"><strong>描述:</strong> {{ item.metadata.description }}</p>
                        <p v-if="item.metadata.file_format"><strong>格式:</strong> {{ item.metadata.file_format }}</p>
                        <a-button 
                          type="link" 
                          size="small" 
                          @click="viewImage(item.metadata.image_path)"
                          style="padding: 0; margin-top: 4px"
                        >
                          查看图片
                        </a-button>
                      </div>
                    </template>
                  </a-alert>
                </div>
                
                <!-- 表格类型特殊展示 -->
                <div v-if="item.type === 'table' && item.metadata?.table_data" class="table-result">
                  <a-alert
                    message="表格结果"
                    type="success"
                    show-icon
                    style="margin-bottom: 8px"
                  >
                    <template #description>
                      <div>
                        <p v-if="item.metadata.table_id"><strong>表格ID:</strong> {{ item.metadata.table_id }}</p>
                        <p v-if="item.metadata.headers?.length > 0">
                          <strong>表头:</strong> {{ item.metadata.headers.join(', ') }}
                        </p>
                        <p v-if="item.metadata.row_count"><strong>行数:</strong> {{ item.metadata.row_count }}</p>
                        <a-button 
                          type="link" 
                          size="small" 
                          @click="viewTable(item.metadata.table_data)"
                          style="padding: 0; margin-top: 4px"
                        >
                          查看表格详情
                        </a-button>
                      </div>
                    </template>
                  </a-alert>
                </div>
                
                <!-- 文本内容展示 -->
                <div v-if="item.content" class="content-text" :class="{ 'expanded': expandedItems.has(index) }">
                  {{ item.content }}
                </div>
                <div v-if="item.content && item.content.length > 200" class="content-actions">
                  <a-button 
                    type="link" 
                    size="small" 
                    @click="toggleExpand(index)"
                  >
                    {{ expandedItems.has(index) ? '收起' : '展开' }}
                  </a-button>
                  <a-button 
                    type="link" 
                    size="small" 
                    @click="copyContent(item.content)"
                  >
                    复制内容
                  </a-button>
                  <a-button 
                    v-if="item.group_id"
                    type="link" 
                    size="small" 
                    @click="viewDocument(item)"
                  >
                    查看文档
                  </a-button>
                </div>
                <div v-if="item.group_id" class="result-meta">
                  <a-tag color="default" size="small">文档: {{ item.group_id }}</a-tag>
                  <a-tag v-if="item.uuid" color="default" size="small">UUID: {{ item.uuid.substring(0, 8) }}...</a-tag>
                  <a-button 
                    v-if="!item.content || item.content.length <= 200"
                    type="link" 
                    size="small" 
                    @click="viewDocument(item)"
                    style="padding: 0; margin-left: 8px"
                  >
                    查看文档
                  </a-button>
                </div>
              </div>
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>

    <!-- 文档详情弹窗 -->
    <a-modal
      v-model:open="documentDetailVisible"
      :title="`查看文档详情 - ${documentDetailData?.group_id || ''}`"
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
import { message, Modal } from 'ant-design-vue'
import { Empty } from 'ant-design-vue'
import { SOURCE_CONFIG, TYPE_CONFIG } from './recall/constants'
import { getDocumentUploadList, getParsedContent, getSummaryContent, getStructuredContent, getChunks } from '../../api/documentUpload'

const props = defineProps({
  results: {
    type: Array,
    default: () => []
  },
  source: {
    type: String,
    default: 'graphiti' // graphiti/cognee/milvus
  }
})

const expandedItems = ref(new Set())

const toggleExpand = (index) => {
  if (expandedItems.value.has(index)) {
    expandedItems.value.delete(index)
  } else {
    expandedItems.value.add(index)
  }
}

const copyContent = async (content) => {
  try {
    await navigator.clipboard.writeText(content)
    message.success('内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

const viewImage = (imagePath) => {
  // 构建图片URL（根据实际API调整）
  const imageUrl = imagePath.startsWith('http') 
    ? imagePath 
    : `/api${imagePath.startsWith('/') ? '' : '/'}${imagePath}`
  
  Modal.info({
    title: '查看图片',
    width: 800,
    content: h('div', [
      h('img', {
        src: imageUrl,
        style: { width: '100%', maxHeight: '600px', objectFit: 'contain' },
        onError: () => {
          message.error('图片加载失败')
        }
      })
    ])
  })
}

const viewTable = (tableData) => {
  // 构建表格展示
  const headers = tableData.headers || []
  const rows = tableData.rows || []
  
  const tableHtml = `
    <div style="max-height: 500px; overflow-y: auto;">
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <thead>
          <tr style="background: #f5f5f5;">
            ${headers.map(h => `<th style="padding: 8px; border: 1px solid #d9d9d9; text-align: left;">${h}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows.slice(0, 20).map(row => `
            <tr>
              ${row.map(cell => `<td style="padding: 8px; border: 1px solid #d9d9d9;">${cell || ''}</td>`).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${rows.length > 20 ? `<p style="margin-top: 8px; color: #999;">（仅显示前20行，共${rows.length}行）</p>` : ''}
    </div>
  `
  
  Modal.info({
    title: tableData.title || '表格详情',
    width: 900,
    content: h('div', {
      innerHTML: tableHtml
    })
  })
}

const getSourceColor = (source) => {
  return SOURCE_CONFIG[source]?.color || 'default'
}

const getSourceLabel = (source) => {
  return SOURCE_CONFIG[source]?.label || source
}

const getTypeColor = (type) => {
  return TYPE_CONFIG[type]?.color || 'default'
}

const getTypeLabel = (type) => {
  return TYPE_CONFIG[type]?.label || type
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
  if (!item.group_id) {
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
    const uploadId = await findUploadIdByGroupId(item.group_id)
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

// 格式化 Markdown（简化版，如果需要完整功能可以引入 markdown-it）
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
.recall-result-list {
  width: 100%;
}

.empty-result {
  margin: 40px 0;
}

.result-list {
  background: #fff;
}

.result-item {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.result-item:hover {
  background-color: #fafafa;
}

.result-header {
  margin-bottom: 8px;
}

.result-name {
  font-weight: 500;
  color: #262626;
}

.source-tag,
.type-tag,
.score-tag {
  font-weight: 500;
}

.result-content {
  margin-top: 8px;
}

.content-text {
  color: #666;
  line-height: 1.6;
  max-height: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.content-text.expanded {
  max-height: none;
  -webkit-line-clamp: unset;
}

.content-actions {
  margin-top: 8px;
}

.result-meta {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>

