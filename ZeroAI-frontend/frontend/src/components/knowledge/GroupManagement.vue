<template>
  <div>
    <!-- 搜索和筛选 -->
    <a-card style="margin-bottom: 16px">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="搜索">
          <a-input
            v-model:value="searchForm.search"
            placeholder="搜索Group ID或文件名"
            style="width: 300px"
            allow-clear
            @pressEnter="handleSearch"
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
      row-key="group_id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'group_id'">
          <a-tooltip :title="record.group_id" placement="topLeft">
            <a-button type="link" @click="handleViewDetail(record)">
              {{ record.group_id }}
            </a-button>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'statistics'">
          <a-space>
            <a-tag color="purple">Episode: {{ record.episode_count || 0 }}</a-tag>
            <a-tag color="green">Entity: {{ record.entity_count || 0 }}</a-tag>
            <a-tag color="blue">Edge: {{ record.edge_count || 0 }}</a-tag>
            <a-tag color="orange">Community: {{ record.community_count || 0 }}</a-tag>
          </a-space>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusLabel(record.status) }}
          </a-tag>
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
      <div v-if="groupDetail" style="max-height: 70vh; overflow-y: auto;">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="Group ID" :span="2">
            <strong>{{ groupDetail.group_id }}</strong>
          </a-descriptions-item>
          
          <!-- 文档信息 -->
          <template v-if="groupDetail.document_info">
            <a-descriptions-item label="文档名称" :span="2">
              {{ groupDetail.document_info.file_name }}
            </a-descriptions-item>
            <a-descriptions-item label="文件大小">
              {{ formatFileSize(groupDetail.document_info.file_size) }}
            </a-descriptions-item>
            <a-descriptions-item label="上传时间">
              {{ formatDateTime(groupDetail.document_info.upload_time) }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="getStatusColor(groupDetail.document_info.status)">
                {{ getStatusLabel(groupDetail.document_info.status) }}
              </a-tag>
            </a-descriptions-item>
          </template>
          <a-descriptions-item label="文档信息" :span="2" v-else>
            <a-typography-text type="secondary">无对应文档记录</a-typography-text>
          </a-descriptions-item>
          
          <!-- 统计信息 -->
          <a-descriptions-item label="统计信息" :span="2">
            <a-row :gutter="16">
              <a-col :span="6">
                <a-statistic
                  title="Episode"
                  :value="groupDetail.statistics?.episode_count || 0"
                  :value-style="{ color: '#722ed1' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="Entity"
                  :value="groupDetail.statistics?.entity_count || 0"
                  :value-style="{ color: '#52c41a' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="Edge"
                  :value="groupDetail.statistics?.edge_count || 0"
                  :value-style="{ color: '#1890ff' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="Community"
                  :value="groupDetail.statistics?.community_count || 0"
                  :value-style="{ color: '#fa8c16' }"
                />
              </a-col>
            </a-row>
          </a-descriptions-item>
        </a-descriptions>
        
        <!-- 快速跳转 -->
        <a-divider>快速跳转</a-divider>
        <a-space wrap>
          <a-button 
            type="primary" 
            @click="handleJumpToTab('community', groupDetail.group_id)"
          >
            查看Community ({{ groupDetail.statistics?.community_count || 0 }})
          </a-button>
          <a-button 
            @click="handleJumpToTab('episode', groupDetail.group_id)"
          >
            查看Episode ({{ groupDetail.statistics?.episode_count || 0 }})
          </a-button>
          <a-button 
            @click="handleJumpToTab('edge', groupDetail.group_id)"
          >
            查看关系 ({{ groupDetail.statistics?.edge_count || 0 }})
          </a-button>
          <a-button 
            @click="handleJumpToTab('entity', groupDetail.group_id)"
          >
            查看实体 ({{ groupDetail.statistics?.entity_count || 0 }})
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { listGroups, getGroupDetail, deleteGroup } from '../../api/knowledgeManagement'

const router = useRouter()

const loading = ref(false)
const dataSource = ref([])
const selectedRowKeys = ref([])
const groupDetail = ref(null)
const detailModalVisible = ref(false)
const detailModalTitle = computed(() => {
  return groupDetail.value ? `Group详情 - ${groupDetail.value.group_id}` : 'Group详情'
})

const searchForm = reactive({
  search: ''
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
    title: 'Group ID',
    key: 'group_id',
    dataIndex: 'group_id',
    width: 300,
    ellipsis: true
  },
  {
    title: '文件名',
    dataIndex: 'file_name',
    ellipsis: true
  },
  {
    title: '统计信息',
    key: 'statistics',
    width: 400
  },
  {
    title: '状态',
    key: 'status',
    dataIndex: 'status',
    width: 100
  },
  {
    title: '上传时间',
    dataIndex: 'upload_time',
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
      search: searchForm.search || undefined
    }
    
    console.log('加载Group列表，参数:', params)
    const response = await listGroups(params)
    console.log('Group列表响应:', response)
    dataSource.value = response.items || []
    pagination.total = response.total || 0
    console.log('Group列表数据:', dataSource.value)
  } catch (error) {
    console.error('加载Group列表失败:', error)
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
  pagination.current = 1
  loadData()
}

const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

const onSelectChange = (keys) => {
  selectedRowKeys.value = keys
}

const handleViewDetail = async (record) => {
  try {
    loading.value = true
    const detail = await getGroupDetail(record.group_id)
    groupDetail.value = detail
    detailModalVisible.value = true
  } catch (error) {
    console.error('获取Group详情失败:', error)
    message.error(`获取详情失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除Group "${record.group_id}" 及其下的所有数据（Episode、Entity、Edge、Community）吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        const result = await deleteGroup(record.group_id)
        message.success(`删除成功：${result.message}`)
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
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 个Group及其下的所有数据吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        let successCount = 0
        let failCount = 0
        
        for (const groupId of selectedRowKeys.value) {
          try {
            await deleteGroup(groupId)
            successCount++
          } catch (error) {
            console.error(`删除Group ${groupId} 失败:`, error)
            failCount++
          }
        }
        
        if (failCount === 0) {
          message.success(`成功删除 ${successCount} 个Group`)
        } else {
          message.warning(`成功删除 ${successCount} 个Group，失败 ${failCount} 个`)
        }
        
        selectedRowKeys.value = []
        loadData()
      } catch (error) {
        console.error('批量删除失败:', error)
        message.error(`批量删除失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

const handleJumpToTab = (tabKey, groupId) => {
  // 跳转到对应的Tab页，并传递groupId参数
  // 这里需要与父组件通信，或者使用路由参数
  // 暂时使用事件通知父组件
  detailModalVisible.value = false
  // 触发自定义事件，通知父组件切换Tab并设置筛选条件
  window.dispatchEvent(new CustomEvent('jump-to-tab', {
    detail: { tabKey, groupId }
  }))
  message.info(`已跳转到${getTabName(tabKey)}，Group ID: ${groupId}`)
}

const getTabName = (tabKey) => {
  const tabNames = {
    'community': 'Community管理',
    'episode': 'Episode管理',
    'edge': '关系管理',
    'entity': '实体管理'
  }
  return tabNames[tabKey] || tabKey
}

const getStatusColor = (status) => {
  const colorMap = {
    'validated': 'green',
    'parsed': 'blue',
    'chunked': 'cyan',
    'completed': 'purple',
    'error': 'red'
  }
  return colorMap[status] || 'default'
}

const getStatusLabel = (status) => {
  const labelMap = {
    'validated': '已验证',
    'parsed': '已解析',
    'chunked': '已分块',
    'completed': '已完成',
    'error': '错误'
  }
  return labelMap[status] || status || '未知'
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

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
</style>

