<template>
  <a-card>
    <template #title>
      <a-space>
        <FolderOutlined />
        <span>文档库</span>
        <a-tag color="blue">{{ statistics.total_documents || 0 }} 个文档</a-tag>
      </a-space>
    </template>
    
    <template #extra>
      <a-space>
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索文档..."
          style="width: 250px"
          @search="handleSearch"
          allow-clear
        />
        <a-button type="primary" @click="handleUpload">
          <template #icon><UploadOutlined /></template>
          上传文档
        </a-button>
        <a-button @click="loadData" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </a-space>
    </template>
    
    <!-- 文档列表 -->
    <div>
        <!-- 批量操作栏 -->
        <div v-if="selectedDocumentIds.length > 0" class="batch-actions">
          <a-space>
            <span>已选择 {{ selectedDocumentIds.length }} 个文档</span>
            <a-button size="small" @click="handleBatchAddToKnowledgeBase">
              <template #icon><BookOutlined /></template>
              添加到知识库
            </a-button>
            <a-button size="small" danger @click="handleBatchDelete">
              <template #icon><DeleteOutlined /></template>
              批量删除
            </a-button>
            <a-button size="small" @click="selectedDocumentIds = []">
              取消选择
            </a-button>
          </a-space>
        </div>
        
        <!-- 文档列表 -->
        <a-table
          :columns="columns"
          :data-source="documents"
          :loading="loading"
          :pagination="pagination"
          :row-selection="{
            selectedRowKeys: selectedDocumentIds,
            onChange: onSelectChange
          }"
          row-key="id"
          @change="handleTableChange"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <!-- 文档名称 -->
            <template v-if="column.key === 'file_name'">
              <a-space>
                <FileWordOutlined v-if="record.file_type === 'docx'" style="color: #2b5797" />
                <FileOutlined v-else />
                <span>{{ record.original_name || record.file_name }}</span>
              </a-space>
            </template>
            
            <!-- 状态 -->
            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusText(record.status) }}
              </a-tag>
            </template>
            
            <!-- 关联知识库 -->
            <template v-if="column.key === 'knowledge_bases'">
              <template v-if="record.knowledge_bases && record.knowledge_bases.length > 0">
                <a-tooltip>
                  <template #title>
                    <div v-for="kb in record.knowledge_bases" :key="kb.id">
                      {{ kb.name }}
                    </div>
                  </template>
                  <a-tag color="blue">
                    {{ record.knowledge_bases.length }} 个知识库
                  </a-tag>
                </a-tooltip>
              </template>
              <a-tag v-else color="default">未分配</a-tag>
            </template>
            
            <!-- 文件大小 -->
            <template v-if="column.key === 'file_size'">
              {{ formatFileSize(record.file_size) }}
            </template>
            
            <!-- 上传时间 -->
            <template v-if="column.key === 'created_at'">
              {{ formatDateTime(record.created_at) }}
            </template>
            
            <!-- 操作 -->
            <template v-if="column.key === 'action'">
              <a-space>
                <a-button type="link" size="small" @click="handlePreview(record)">
                  <template #icon><EyeOutlined /></template>
                  预览
                </a-button>
                <a-button type="link" size="small" @click="handleDownload(record)">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
                <a-dropdown>
                  <a-button type="link" size="small">
                    更多
                    <DownOutlined />
                  </a-button>
                  <template #overlay>
                    <a-menu @click="({ key }) => handleDocumentAction(key, record)">
                      <a-menu-item key="addToKb">
                        <BookOutlined /> 添加到知识库
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger>
                        <DeleteOutlined /> 删除
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </a-space>
            </template>
          </template>
        </a-table>
    </div>
    
    <!-- 上传文档弹窗 -->
    <a-modal
      v-model:open="uploadModalVisible"
      title="上传文档"
      @ok="handleUploadConfirm"
      :confirm-loading="uploading"
      :ok-button-props="{ disabled: fileList.length === 0 }"
    >
      <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="选择文件">
          <a-upload-dragger
            v-model:fileList="fileList"
            :multiple="true"
            :before-upload="() => false"
            accept=".doc,.docx"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p class="ant-upload-hint">支持 .doc, .docx 格式</p>
          </a-upload-dragger>
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- 添加到知识库弹窗 -->
    <a-modal
      v-model:open="addToKbModalVisible"
      title="添加到知识库"
      @ok="handleAddToKbConfirm"
      :confirm-loading="addingToKb"
    >
      <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="选择知识库" required>
          <a-select
            v-model:value="selectedKnowledgeBaseId"
            placeholder="请选择知识库"
            style="width: 100%"
            :loading="loadingKnowledgeBases"
            show-search
            :filter-option="filterKnowledgeBase"
          >
            <a-select-option
              v-for="kb in knowledgeBases"
              :key="kb.id"
              :value="kb.id"
            >
              {{ kb.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="选中文档">
          <div style="color: #666">
            {{ pendingDocuments.length }} 个文档将被添加到知识库
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
    
  </a-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  FolderOutlined,
  UploadOutlined,
  ReloadOutlined,
  DeleteOutlined,
  FileWordOutlined,
  FileOutlined,
  EyeOutlined,
  DownloadOutlined,
  DownOutlined,
  BookOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'
import {
  getDocuments,
  uploadDocument,
  uploadDocumentsBatch,
  deleteDocument,
  deleteDocumentsBatch,
  addDocumentToKnowledgeBase,
  addDocumentsToKnowledgeBaseBatch,
  getStatistics,
  searchDocuments
} from '@/api/documentLibrary'
import { getKnowledgeBases } from '@/api/knowledgeBase'

// 状态
const loading = ref(false)
const documents = ref([])
const statistics = ref({})
const searchKeyword = ref('')
const selectedDocumentIds = ref([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

// 表格列定义
const columns = [
  { title: '文档名称', key: 'file_name', ellipsis: true },
  { title: '状态', key: 'status', width: 100 },
  { title: '关联知识库', key: 'knowledge_bases', width: 120 },
  { title: '文件大小', key: 'file_size', width: 100 },
  { title: '上传时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

// 上传相关
const uploadModalVisible = ref(false)
const uploading = ref(false)
const fileList = ref([])

// 添加到知识库相关
const addToKbModalVisible = ref(false)
const addingToKb = ref(false)
const selectedKnowledgeBaseId = ref(null)
const knowledgeBases = ref([])
const loadingKnowledgeBases = ref(false)
const pendingDocuments = ref([])

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadDocuments(),
      loadStatistics()
    ])
  } finally {
    loading.value = false
  }
}

const loadDocuments = async () => {
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    
    // 搜索关键词
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    const res = await getDocuments(params)
    // 后端返回格式：{ success: true, data: { items: [...], total: ... } }
    if (res && res.data) {
      documents.value = res.data.items || []
      pagination.total = res.data.total || 0
    } else {
      // 兼容旧格式
      documents.value = res.documents || []
      pagination.total = res.total || 0
    }
  } catch (error) {
    console.error('加载文档失败:', error)
    message.error('加载文档失败')
  }
}

const loadStatistics = async () => {
  try {
    const res = await getStatistics()
    // 后端返回格式：{ success: true, data: {...} } 或直接返回数据
    if (res && res.data) {
      statistics.value = res.data || {}
    } else {
      statistics.value = res || {}
    }
  } catch (error) {
    console.error('加载统计信息失败:', error)
  }
}

const loadKnowledgeBases = async () => {
  loadingKnowledgeBases.value = true
  try {
    const res = await getKnowledgeBases({ page_size: 100 })
    knowledgeBases.value = res.knowledge_bases || []
  } catch (error) {
    console.error('加载知识库失败:', error)
  } finally {
    loadingKnowledgeBases.value = false
  }
}

// 事件处理
const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadDocuments()
}

const onSelectChange = (keys) => {
  selectedDocumentIds.value = keys
}

const handleSearch = () => {
  pagination.current = 1
  loadDocuments()
}

// 上传文档
const handleUpload = () => {
  fileList.value = []
  uploadModalVisible.value = true
}

const handleUploadConfirm = async () => {
  if (fileList.value.length === 0) {
    message.warning('请选择文件')
    return
  }
  
  uploading.value = true
  try {
    if (fileList.value.length === 1) {
      await uploadDocument(fileList.value[0].originFileObj, null)
    } else {
      await uploadDocumentsBatch(
        fileList.value.map(f => f.originFileObj),
        null
      )
    }
    message.success('上传成功')
    uploadModalVisible.value = false
    loadData()
  } catch (error) {
    console.error('上传失败:', error)
    message.error('上传失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploading.value = false
  }
}

// 文档操作
const handleDocumentAction = (action, record) => {
  if (action === 'addToKb') {
    pendingDocuments.value = [record]
    selectedKnowledgeBaseId.value = null
    loadKnowledgeBases()
    addToKbModalVisible.value = true
  } else if (action === 'delete') {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文档"${record.original_name || record.file_name}"吗？`,
      onOk: async () => {
        try {
          await deleteDocument(record.id)
          message.success('删除成功')
          loadData()
        } catch (error) {
          message.error('删除失败: ' + (error.response?.data?.detail || error.message))
        }
      }
    })
  }
}

const handlePreview = (record) => {
  // 打开预览窗口
  window.open(`/api/document-library/documents/${record.id}/preview`, '_blank')
}

const handleDownload = (record) => {
  // 下载文件
  window.open(`/api/document-library/documents/${record.id}/download`, '_blank')
}

// 批量操作
const handleBatchAddToKnowledgeBase = () => {
  pendingDocuments.value = documents.value.filter(d => selectedDocumentIds.value.includes(d.id))
  selectedKnowledgeBaseId.value = null
  loadKnowledgeBases()
  addToKbModalVisible.value = true
}

const handleBatchDelete = () => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除选中的 ${selectedDocumentIds.value.length} 个文档吗？`,
    onOk: async () => {
      try {
        await deleteDocumentsBatch(selectedDocumentIds.value)
        message.success('删除成功')
        selectedDocumentIds.value = []
        loadData()
      } catch (error) {
        message.error('删除失败: ' + (error.response?.data?.detail || error.message))
      }
    }
  })
}

// 添加到知识库
const handleAddToKbConfirm = async () => {
  if (!selectedKnowledgeBaseId.value) {
    message.warning('请选择知识库')
    return
  }
  
  addingToKb.value = true
  try {
    const documentIds = pendingDocuments.value.map(d => d.id)
    if (documentIds.length === 1) {
      await addDocumentToKnowledgeBase(documentIds[0], selectedKnowledgeBaseId.value)
    } else {
      await addDocumentsToKnowledgeBaseBatch(documentIds, selectedKnowledgeBaseId.value)
    }
    message.success('添加成功')
    addToKbModalVisible.value = false
    selectedDocumentIds.value = []
    loadData()
  } catch (error) {
    message.error('添加失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    addingToKb.value = false
  }
}


// 辅助函数
const getStatusColor = (status) => {
  const colors = {
    'pending': 'default',
    'processing': 'processing',
    'completed': 'success',
    'failed': 'error'
  }
  return colors[status] || 'default'
}

const getStatusText = (status) => {
  const texts = {
    'pending': '待处理',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败'
  }
  return texts[status] || status
}

const formatFileSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const filterKnowledgeBase = (input, option) => {
  return option.children[0].children.toLowerCase().includes(input.toLowerCase())
}

// 初始化
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.batch-actions {
  background: #e6f7ff;
  padding: 12px 16px;
  border-radius: 4px;
  margin-bottom: 16px;
}
</style>

