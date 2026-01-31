<template>
  <div>
    <!-- 搜索和筛选 -->
    <a-card style="margin-bottom: 16px">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="搜索">
          <a-input
            v-model:value="searchForm.search"
            placeholder="搜索名称或内容"
            style="width: 200px"
            allow-clear
            @pressEnter="handleSearch"
          />
        </a-form-item>
        <a-form-item label="Group ID">
          <a-input
            v-model:value="searchForm.group_id"
            placeholder="筛选Group ID"
            style="width: 200px"
            allow-clear
            :disabled="!!props.groupId"
          />
        </a-form-item>
        <a-form-item label="来源">
          <a-select
            v-model:value="searchForm.source_description"
            placeholder="筛选来源"
            style="width: 150px"
            allow-clear
          >
            <a-select-option value="Word文档章节">Word文档章节</a-select-option>
            <a-select-option value="Word文档图片">Word文档图片</a-select-option>
            <a-select-option value="Word文档表格">Word文档表格</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="创建时间">
          <a-range-picker
            v-model:value="searchForm.dateRange"
            format="YYYY-MM-DD"
            @change="handleDateRangeChange"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">搜索</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 操作栏 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center">
      <div>
        <a-button 
          type="primary" 
          danger 
          :disabled="selectedRowKeys.length === 0"
          @click="handleBatchDelete"
        >
          批量删除 ({{ selectedRowKeys.length }})
        </a-button>
      </div>
      <div>
        <a-button @click="loadData">刷新</a-button>
      </div>
    </div>

    <!-- 数据表格 -->
    <a-table
      :columns="columns"
      :data-source="dataSource"
      :loading="loading"
      :pagination="pagination"
      :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
      row-key="uuid"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a-tooltip :title="record.name || '未知'" placement="topLeft">
            <a-button type="link" @click="handleViewDetail(record)">
              {{ record.name || '未知' }}
            </a-button>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'content'">
          <div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            {{ record.content_preview || record.content || '' }}
          </div>
        </template>
        <template v-else-if="column.key === 'source_description'">
          <a-tag color="purple">{{ record.source_description || '-' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleViewDetail(record)">查看详情</a-button>
            <a-button type="link" size="small" danger @click="handleDelete(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 详情模态框 -->
    <a-modal
      v-model:open="detailModalVisible"
      :title="detailModalTitle"
      width="1000px"
      :footer="null"
    >
      <div v-if="selectedItem" style="max-height: 70vh; overflow-y: auto;">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="UUID" :span="2">
            {{ selectedItem.uuid }}
          </a-descriptions-item>
          <a-descriptions-item label="名称" :span="2">
            {{ selectedItem.name || '未知' }}
          </a-descriptions-item>
          <a-descriptions-item label="来源" v-if="selectedItem.source_description">
            <a-tag color="purple">{{ selectedItem.source_description }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedItem.group_id">
            {{ selectedItem.group_id }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" v-if="selectedItem.created_at">
            {{ formatDateTime(selectedItem.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="完整内容" :span="2" v-if="selectedItem.content">
            <div 
              v-html="formatMarkdown(selectedItem.content)"
              style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: 400px; overflow-y: auto;"
            ></div>
          </a-descriptions-item>
          <a-descriptions-item label="完整属性" :span="2" v-if="selectedItem.properties">
            <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; max-height: 300px; overflow-y: auto; font-size: 12px;">{{ formatProperties(selectedItem.properties) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  groupId: {
    type: String,
    default: null
  }
})
import { message, Modal } from 'ant-design-vue'
import { listEpisodes, deleteEpisodes } from '../../api/knowledgeManagement'

const loading = ref(false)
const dataSource = ref([])
const selectedRowKeys = ref([])
const selectedItem = ref(null)
const detailModalVisible = ref(false)
const detailModalTitle = computed(() => {
  return selectedItem.value ? `Episode详情 - ${selectedItem.value.name || '未知'}` : 'Episode详情'
})

const searchForm = reactive({
  search: '',
  group_id: '',
  source_description: undefined,
  dateRange: null
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 条`
})

const columns = [
  {
    title: '名称',
    key: 'name',
    dataIndex: 'name',
    width: 250,
    ellipsis: true
  },
  {
    title: '内容预览',
    key: 'content',
    dataIndex: 'content_preview',
    ellipsis: true
  },
  {
    title: '来源',
    key: 'source_description',
    dataIndex: 'source_description',
    width: 150
  },
  {
    title: 'Group ID',
    dataIndex: 'group_id',
    width: 200,
    ellipsis: true
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 180
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    fixed: 'right'
  }
]

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      search: searchForm.search || undefined,
      group_id: searchForm.group_id || undefined,
      source_description: searchForm.source_description || undefined,
      start_date: searchForm.dateRange?.[0]?.format('YYYY-MM-DD') || undefined,
      end_date: searchForm.dateRange?.[1]?.format('YYYY-MM-DD') || undefined
    }
    
    const response = await listEpisodes(params)
    dataSource.value = response.items || []
    pagination.total = response.total || 0
  } catch (error) {
    console.error('加载Episode列表失败:', error)
    message.error(`加载失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  loadData()
}

const handleReset = () => {
  searchForm.search = ''
  searchForm.group_id = ''
  searchForm.source_description = undefined
  searchForm.dateRange = null
  pagination.current = 1
  loadData()
}

const handleDateRangeChange = () => {
  handleSearch()
}

const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

const onSelectChange = (keys) => {
  selectedRowKeys.value = keys
}

const handleViewDetail = (record) => {
  selectedItem.value = record
  detailModalVisible.value = true
}

const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除Episode "${record.name || record.uuid}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        await deleteEpisodes([record.uuid])
        message.success('删除成功')
        loadData()
      } catch (error) {
        console.error('删除失败:', error)
        message.error(`删除失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

const handleBatchDelete = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要删除的项')
    return
  }
  
  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 个Episode吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        await deleteEpisodes(selectedRowKeys.value)
        message.success('批量删除成功')
        selectedRowKeys.value = []
        loadData()
      } catch (error) {
        console.error('批量删除失败:', error)
        message.error(`批量删除失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return ''
  try {
    const date = new Date(dateTime)
    return date.toLocaleString('zh-CN')
  } catch (e) {
    return String(dateTime)
  }
}

const formatProperties = (properties) => {
  if (!properties) return ''
  try {
    const filtered = { ...properties }
    delete filtered.name_embedding
    return JSON.stringify(filtered, null, 2)
  } catch (e) {
    return String(properties)
  }
}

// 格式化Markdown内容为HTML
const formatMarkdown = (text) => {
  if (!text) return ''
  
  const escapeHtml = (str) => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }
  
  // 处理Markdown表格
  const tableRegex = /(\|.+\|(?:\s*\n\s*\|[:\-\s\|]+\|)?(?:\s*\n\s*\|.+\|)+)/g
  let processedText = text.replace(tableRegex, (match) => {
    const lines = match.trim().split('\n').filter(line => line.trim())
    if (lines.length < 2) return match
    
    const headerLine = lines[0].trim()
    const headers = headerLine.split('|').map(h => h.trim()).filter(h => h)
    
    let dataStartIndex = 1
    if (lines[1].trim().match(/^[\|\s\-\:]+$/)) {
      dataStartIndex = 2
    }
    
    const rows = []
    for (let i = dataStartIndex; i < lines.length; i++) {
      const cells = lines[i].split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx < lines[i].split('|').length - 1)
      if (cells.length > 0) {
        rows.push(cells)
      }
    }
    
    let htmlTable = '<table style="border-collapse: collapse; width: 100%; margin: 16px 0; border: 1px solid #d9d9d9;">'
    htmlTable += '<thead><tr style="background: #fafafa;">'
    headers.forEach(header => {
      htmlTable += `<th style="border: 1px solid #d9d9d9; padding: 8px 12px; text-align: left; font-weight: 600;">${escapeHtml(header)}</th>`
    })
    htmlTable += '</tr></thead>'
    htmlTable += '<tbody>'
    rows.forEach(row => {
      htmlTable += '<tr>'
      headers.forEach((_, colIndex) => {
        const cellContent = row[colIndex] || ''
        htmlTable += `<td style="border: 1px solid #d9d9d9; padding: 8px 12px;">${escapeHtml(cellContent)}</td>`
      })
      htmlTable += '</tr>'
    })
    htmlTable += '</tbody></table>'
    return htmlTable
  })
  
  // 处理Markdown图片
  processedText = processedText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    if (url.includes('/images/') || url.startsWith('/api/document-upload/') || url.startsWith('/api/word-document/')) {
      const linkText = alt || '图片'
      return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline; display: inline-block; margin: 8px 0;">
        <img src="${url}" alt="${escapeHtml(linkText)}" style="max-width: 100%; height: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 4px; background: #fafafa;" 
        onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">
        <span style="display: none;">${escapeHtml(linkText)}</span>
      </a>`
    }
    return `<img src="${url}" alt="${escapeHtml(alt || '')}" style="max-width: 100%; height: auto; margin: 8px 0;">`
  })
  
  // 处理Markdown链接
  processedText = processedText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    if (match.includes('<img')) return match
    return `<a href="${url}" target="_blank" style="color: #1890ff; text-decoration: underline;">${escapeHtml(linkText)}</a>`
  })
  
  // 处理标题
  processedText = processedText.replace(/^#### (.*$)/gim, '<h4 style="margin: 16px 0 8px 0; font-size: 16px; font-weight: 600;">$1</h4>')
  processedText = processedText.replace(/^### (.*$)/gim, '<h3 style="margin: 20px 0 12px 0; font-size: 18px; font-weight: 600;">$1</h3>')
  processedText = processedText.replace(/^## (.*$)/gim, '<h2 style="margin: 24px 0 16px 0; font-size: 20px; font-weight: 600;">$1</h2>')
  processedText = processedText.replace(/^# (.*$)/gim, '<h1 style="margin: 28px 0 20px 0; font-size: 24px; font-weight: 600;">$1</h1>')
  
  // 处理粗体
  processedText = processedText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  
  // 处理斜体
  processedText = processedText.replace(/\*([^\*]+)\*/g, '<em>$1</em>')
  
  // 处理代码块
  processedText = processedText.replace(/```([^`]+)```/g, '<pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; margin: 12px 0;"><code>$1</code></pre>')
  
  // 处理行内代码
  processedText = processedText.replace(/`([^`]+)`/g, '<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>')
  
  // 处理列表项
  processedText = processedText.replace(/^[\-\*\+] (.+)$/gim, '<li style="margin: 4px 0;">$1</li>')
  processedText = processedText.replace(/(<li[^>]*>.*?<\/li>(?:\s*<li[^>]*>.*?<\/li>)*)/gs, '<ul style="margin: 8px 0; padding-left: 24px;">$1</ul>')
  
  // 处理换行
  processedText = processedText.replace(/\n\n/g, '<br><br>')
  processedText = processedText.replace(/\n/g, '<br>')
  
  return processedText
}

// 监听props.groupId变化
watch(() => props.groupId, (newGroupId) => {
  if (newGroupId) {
    searchForm.group_id = newGroupId
    pagination.current = 1
    loadData()
  }
}, { immediate: true })

// 监听设置Group筛选条件的事件
const handleSetGroupFilter = (event) => {
  const { groupId } = event.detail
  if (groupId) {
    searchForm.group_id = groupId
    pagination.current = 1
    loadData()
  }
}

onMounted(() => {
  if (props.groupId) {
    searchForm.group_id = props.groupId
  }
  loadData()
  
  // 监听设置Group筛选条件的事件
  window.addEventListener('set-group-filter', handleSetGroupFilter)
})

onUnmounted(() => {
  window.removeEventListener('set-group-filter', handleSetGroupFilter)
})
</script>

<style scoped>
</style>

