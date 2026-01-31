<template>
  <a-card>
    <template #title>
      <span>任务管理</span>
    </template>
    
    <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
      <a-select
        v-model:value="filterStatus"
        placeholder="筛选状态"
        style="width: 150px"
        allow-clear
        @change="loadTaskList"
      >
        <a-select-option value="pending">待处理</a-select-option>
        <a-select-option value="running">运行中</a-select-option>
        <a-select-option value="completed">已完成</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
        <a-select-option value="cancelled">已取消</a-select-option>
      </a-select>
      
      <a-input-number
        v-model:value="filterUploadId"
        placeholder="文档ID"
        style="width: 150px"
        :min="1"
        allow-clear
        @change="loadTaskList"
      />
      
      <a-button @click="loadTaskList" :loading="loading">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>
    
    <a-table
      :columns="columns"
      :data-source="tasks"
      :loading="loading"
      :pagination="pagination"
      row-key="task_id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>
        
        <template v-if="column.key === 'progress'">
          <a-progress
            :percent="record.progress"
            :status="record.status === 'failed' ? 'exception' : record.status === 'completed' ? 'success' : 'active'"
            :format="(percent) => `${percent}%`"
          />
        </template>
        
        <template v-if="column.key === 'current_step'">
          <span :title="record.current_step">{{ record.current_step || '-' }}</span>
        </template>
        
        <template v-if="column.key === 'created_at'">
          {{ formatDateTime(record.created_at) }}
        </template>
        
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button
              type="link"
              size="small"
              @click="handleViewDetail(record)"
            >
              查看详情
            </a-button>
            <a-button
              v-if="record.status === 'pending' || record.status === 'running'"
              type="link"
              size="small"
              danger
              @click="handleCancel(record)"
            >
              取消
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
    
    <!-- 任务详情Modal -->
    <a-modal
      v-model:open="detailModalVisible"
      title="任务详情"
      width="1000px"
      :footer="null"
    >
      <div v-if="selectedTask">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="任务ID">{{ selectedTask.task_id }}</a-descriptions-item>
          <a-descriptions-item label="文档ID">{{ selectedTask.upload_id }}</a-descriptions-item>
          <a-descriptions-item label="文档名称">{{ selectedTask.document_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="任务类型">{{ getTaskTypeText(selectedTask.task_type) }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="getStatusColor(selectedTask.status)">
              {{ getStatusText(selectedTask.status) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="进度">
            <a-progress
              :percent="selectedTask.progress"
              :status="selectedTask.status === 'failed' ? 'exception' : selectedTask.status === 'completed' ? 'success' : 'active'"
            />
          </a-descriptions-item>
          <a-descriptions-item label="当前步骤" :span="2">
            {{ selectedTask.current_step || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="步骤进度">
            {{ selectedTask.completed_steps }} / {{ selectedTask.total_steps }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(selectedTask.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ selectedTask.started_at ? formatDateTime(selectedTask.started_at) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="完成时间">{{ selectedTask.completed_at ? formatDateTime(selectedTask.completed_at) : '-' }}</a-descriptions-item>
        </a-descriptions>
        
        <div v-if="selectedTask.error_message" style="margin-top: 16px">
          <a-alert
            type="error"
            :message="selectedTask.error_message"
            show-icon
          />
        </div>
        
        <!-- 构建Community结果展示 -->
        <div v-if="isBuildCommunitiesTask && selectedTask.result" style="margin-top: 16px">
          <a-divider orientation="left">构建结果</a-divider>
          <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
            <a-descriptions-item label="Community数量">
              <a-tag color="blue">{{ selectedTask.result.statistics?.total_communities || 0 }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="包含实体总数">
              <a-tag color="green">{{ selectedTask.result.statistics?.total_entities || 0 }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="翻译数量" v-if="selectedTask.result.statistics?.translated_count !== undefined">
              <a-tag color="orange">{{ selectedTask.result.statistics.translated_count }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="构建范围">
              <a-tag>{{ selectedTask.result.statistics?.scope === 'current' ? '当前文档' : '跨文档' }}</a-tag>
            </a-descriptions-item>
          </a-descriptions>
          
          <a-table
            :columns="[
              { title: 'UUID', dataIndex: 'uuid', key: 'uuid', ellipsis: true, width: 200 },
              { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
              { title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true, width: 300 },
              { title: '实体数量', dataIndex: 'entity_count', key: 'entity_count', width: 100 },
              { title: 'Group IDs', dataIndex: 'group_ids', key: 'group_ids', ellipsis: true }
            ]"
            :data-source="selectedTask.result.communities || []"
            :pagination="{ pageSize: 10 }"
            size="small"
            bordered
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'group_ids'">
                <a-tag v-for="(gid, idx) in (record.group_ids || [])" :key="idx" style="margin-right: 4px">
                  {{ gid }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>

        <!-- 生成的需求文档展示 -->
        <div v-if="isGeneratedDocument && selectedTask.result" style="margin-top: 16px">
          <a-card title="生成的文档" :bordered="false">
            <template #extra>
              <a-space>
                <a-button type="primary" @click="handleDownloadDocument('markdown')">
                  <template #icon><DownloadOutlined /></template>
                  下载Markdown
                </a-button>
                <a-button type="primary" @click="handleDownloadDocument('docx')">
                  <template #icon><DownloadOutlined /></template>
                  下载DOCX
                </a-button>
                <a-button @click="handleCopyDocument">
                  <template #icon><CopyOutlined /></template>
                  复制内容
                </a-button>
              </a-space>
            </template>
            
            <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
              <a-descriptions-item label="文档ID">{{ selectedTask.result.document_id }}</a-descriptions-item>
              <a-descriptions-item label="文档名称">{{ selectedTask.result.document_name }}</a-descriptions-item>
              <a-descriptions-item label="格式">{{ selectedTask.result.format }}</a-descriptions-item>
              <a-descriptions-item label="质量评分">
                <a-tag color="green">{{ selectedTask.result.quality_score?.toFixed(1) || '-' }}分</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="迭代次数">{{ selectedTask.result.iteration_count || '-' }}</a-descriptions-item>
              <a-descriptions-item label="检索内容数">{{ selectedTask.result.retrieved_content_count || '-' }}</a-descriptions-item>
            </a-descriptions>
            
            <a-divider>文档内容</a-divider>
            
            <div style="max-height: 500px; overflow-y: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 16px; background: #fafafa">
              <div v-if="selectedTask.result.format === 'markdown'" v-html="formatMarkdown(selectedTask.result.content)"></div>
              <pre v-else style="white-space: pre-wrap; word-wrap: break-word; margin: 0">{{ selectedTask.result.content }}</pre>
            </div>
          </a-card>
        </div>
        
        <!-- 其他任务结果（JSON格式） -->
        <div v-else-if="selectedTask.result" style="margin-top: 16px">
          <a-collapse>
            <a-collapse-panel key="result" header="任务结果">
              <pre style="max-height: 400px; overflow: auto">{{ JSON.stringify(selectedTask.result, null, 2) }}</pre>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </div>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, DownloadOutlined, CopyOutlined } from '@ant-design/icons-vue'
import { getTaskList, cancelTask, getTask, downloadTaskDocumentDocx } from '../api/taskManagement'

const loading = ref(false)
const tasks = ref([])
const filterStatus = ref(null)
const filterUploadId = ref(null)
const selectedTask = ref(null)
const detailModalVisible = ref(false)
const pollInterval = ref(null)

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true,
  showQuickJumper: true
})

const columns = [
  {
    title: '任务ID',
    dataIndex: 'task_id',
    key: 'task_id',
    ellipsis: true,
    width: 200
  },
  {
    title: '文档ID',
    dataIndex: 'upload_id',
    key: 'upload_id',
    width: 100
  },
  {
    title: '文档名称',
    dataIndex: 'document_name',
    key: 'document_name',
    ellipsis: true
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100
  },
  {
    title: '进度',
    dataIndex: 'progress',
    key: 'progress',
    width: 150
  },
  {
    title: '当前步骤',
    dataIndex: 'current_step',
    key: 'current_step',
    ellipsis: true
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    fixed: 'right'
  }
]

const getStatusColor = (status) => {
  const colorMap = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
    cancelled: 'warning'
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status) => {
  const textMap = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return textMap[status] || status
}

const getTaskTypeText = (taskType) => {
  const textMap = {
    process_document: '处理文档',
    generate_requirement_document: '生成需求文档',
    build_communities: '构建Community'
  }
  return textMap[taskType] || taskType
}

// 判断是否为生成的需求文档任务
const isGeneratedDocument = computed(() => {
  return selectedTask.value?.task_type === 'generate_requirement_document' 
    && selectedTask.value?.status === 'completed'
    && selectedTask.value?.result
})

// 判断是否为构建Community任务
const isBuildCommunitiesTask = computed(() => {
  return selectedTask.value?.task_type === 'build_communities' 
    && selectedTask.value?.status === 'completed'
    && selectedTask.value?.result
})

// 简单的Markdown格式化（基础支持）
const formatMarkdown = (text) => {
  if (!text) return ''
  // 简单的Markdown转HTML（基础实现）
  return text
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/^\*(.*)\*/gim, '<em>$1</em>')
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
    .replace(/\n/g, '<br>')
}

// 下载文档
const handleDownloadDocument = async (format = 'markdown') => {
  if (!selectedTask.value?.result) return
  
  const result = selectedTask.value.result
  const documentName = result.document_name || '需求文档'
  
  if (format === 'docx') {
    // 下载DOCX格式
    try {
      const response = await downloadTaskDocumentDocx(selectedTask.value.task_id)
      const blob = new Blob([response], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${documentName}.docx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      message.success('DOCX文档下载成功')
    } catch (error) {
      console.error('下载DOCX失败:', error)
      message.error(`下载DOCX失败: ${error.message || '未知错误'}`)
    }
  } else {
    // 下载Markdown格式
    const content = result.content || ''
    const fileName = `${documentName}.md`
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    message.success('Markdown文档下载成功')
  }
}

// 复制文档内容
const handleCopyDocument = async () => {
  if (!selectedTask.value?.result?.content) return
  
  try {
    await navigator.clipboard.writeText(selectedTask.value.result.content)
    message.success('文档内容已复制到剪贴板')
  } catch (error) {
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = selectedTask.value.result.content
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    message.success('文档内容已复制到剪贴板')
  }
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const loadTaskList = async () => {
  loading.value = true
  try {
    const response = await getTaskList(
      pagination.value.current,
      pagination.value.pageSize,
      filterStatus.value,
      filterUploadId.value
    )
    tasks.value = response.items || []
    pagination.value.total = response.total || 0
    
    // 更新运行中任务的详细信息
    for (const task of tasks.value) {
      if (task.status === 'running' || task.status === 'pending') {
        try {
          const taskDetail = await getTask(task.task_id)
          Object.assign(task, taskDetail)
        } catch (e) {
          console.error('获取任务详情失败:', e)
        }
      }
    }
  } catch (error) {
    console.error('加载任务列表失败:', error)
    message.error(`加载失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadTaskList()
}

const handleViewDetail = async (task) => {
  try {
    const taskDetail = await getTask(task.task_id)
    selectedTask.value = taskDetail
    detailModalVisible.value = true
  } catch (error) {
    console.error('获取任务详情失败:', error)
    message.error(`获取详情失败: ${error.message || '未知错误'}`)
  }
}

const handleCancel = async (task) => {
  try {
    await cancelTask(task.task_id)
    message.success('任务已取消')
    loadTaskList()
  } catch (error) {
    console.error('取消任务失败:', error)
    message.error(`取消失败: ${error.message || '未知错误'}`)
  }
}

// 轮询更新运行中的任务
const startPolling = () => {
  pollInterval.value = setInterval(() => {
    // 只更新运行中的任务
    const runningTasks = tasks.value.filter(t => t.status === 'running' || t.status === 'pending')
    if (runningTasks.length > 0) {
      loadTaskList()
    }
  }, 2000) // 每2秒更新一次
}

const stopPolling = () => {
  if (pollInterval.value) {
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}

onMounted(() => {
  loadTaskList()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
</style>

