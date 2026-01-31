<template>
  <div>
    <!-- 搜索和筛选 -->
    <a-card style="margin-bottom: 16px">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="搜索">
          <a-input
            v-model:value="searchForm.search"
            placeholder="搜索关系名称或描述"
            style="width: 200px"
            allow-clear
            @pressEnter="handleSearch"
          />
        </a-form-item>
        <a-form-item label="关系类型">
          <a-select
            v-model:value="searchForm.rel_type"
            placeholder="筛选关系类型"
            style="width: 150px"
            allow-clear
          >
            <a-select-option value="RELATES_TO">RELATES_TO</a-select-option>
            <a-select-option value="MENTIONS">MENTIONS</a-select-option>
            <a-select-option value="CONTAINS">CONTAINS</a-select-option>
            <a-select-option value="HAS_MEMBER">HAS_MEMBER</a-select-option>
          </a-select>
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
        <template v-if="column.key === 'rel_type'">
          <a-tooltip :title="record.rel_type" placement="topLeft">
            <a-tag color="blue">{{ record.rel_type }}</a-tag>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'source_target'">
          <span>
            <strong>{{ record.source_name || `节点${record.source_id}` }}</strong>
            <ArrowRightOutlined style="margin: 0 8px" />
            <strong>{{ record.target_name || `节点${record.target_id}` }}</strong>
          </span>
        </template>
        <template v-else-if="column.key === 'fact'">
          <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            {{ record.fact || '-' }}
          </div>
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
          <a-descriptions-item label="关系类型" :span="2">
            <a-tag color="blue">{{ selectedItem.rel_type }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="源节点" :span="2">
            {{ selectedItem.source_name || `节点${selectedItem.source_id}` }}
            <a-tag v-if="selectedItem.source_labels && selectedItem.source_labels.length > 0" style="margin-left: 8px">
              {{ selectedItem.source_labels[0] }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="目标节点" :span="2">
            {{ selectedItem.target_name || `节点${selectedItem.target_id}` }}
            <a-tag v-if="selectedItem.target_labels && selectedItem.target_labels.length > 0" style="margin-left: 8px">
              {{ selectedItem.target_labels[0] }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="关系描述" :span="2" v-if="selectedItem.fact">
            {{ selectedItem.fact }}
          </a-descriptions-item>
          <a-descriptions-item label="关系名称" v-if="selectedItem.name">
            {{ selectedItem.name }}
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedItem.group_id">
            {{ selectedItem.group_id }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" v-if="selectedItem.created_at">
            {{ formatDateTime(selectedItem.created_at) }}
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
import { ArrowRightOutlined } from '@ant-design/icons-vue'
import { listEdges, deleteEdges } from '../../api/knowledgeManagement'

const loading = ref(false)
const dataSource = ref([])
const selectedRowKeys = ref([])
const selectedItem = ref(null)
const detailModalVisible = ref(false)
const detailModalTitle = computed(() => {
  if (!selectedItem.value) return '关系详情'
  return `关系详情 - ${selectedItem.value.rel_type || '未知'}`
})

const searchForm = reactive({
  search: '',
  rel_type: undefined,
  group_id: '',
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
    title: '关系类型',
    key: 'rel_type',
    dataIndex: 'rel_type',
    width: 120
  },
  {
    title: '源节点 → 目标节点',
    key: 'source_target',
    width: 300
  },
  {
    title: '关系描述',
    key: 'fact',
    dataIndex: 'fact',
    ellipsis: true
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
      rel_type: searchForm.rel_type || undefined,
      group_id: searchForm.group_id || undefined,
      start_date: searchForm.dateRange?.[0]?.format('YYYY-MM-DD') || undefined,
      end_date: searchForm.dateRange?.[1]?.format('YYYY-MM-DD') || undefined
    }
    
    const response = await listEdges(params)
    dataSource.value = response.items || []
    pagination.total = response.total || 0
  } catch (error) {
    console.error('加载关系列表失败:', error)
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
  searchForm.rel_type = undefined
  searchForm.group_id = ''
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
    content: `确定要删除关系 "${record.rel_type}" (${record.source_name || record.source_id} → ${record.target_name || record.target_id}) 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        await deleteEdges([record.uuid])
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
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 个关系吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        await deleteEdges(selectedRowKeys.value)
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

