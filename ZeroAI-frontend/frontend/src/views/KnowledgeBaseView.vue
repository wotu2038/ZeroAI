<template>
  <a-card>
    <template #title>
      <span>知识库管理</span>
    </template>
    
    <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; justify-content: space-between">
      <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
        <a-select
          v-model:value="filterType"
          placeholder="筛选类型"
          style="width: 150px"
          @change="loadKnowledgeBases"
        >
          <a-select-option value="my_created">我创建的</a-select-option>
          <a-select-option value="my_joined">我加入的</a-select-option>
          <a-select-option value="shared">共享知识库</a-select-option>
        </a-select>
        
        <a-button type="primary" @click="handleCreate">
          <template #icon><PlusOutlined /></template>
          创建知识库
        </a-button>
        
        <a-button @click="loadKnowledgeBases" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </div>
      
      <div v-if="currentUser" style="display: flex; align-items: center; gap: 8px">
        <span>当前用户：{{ currentUser.username }}</span>
        <a-button size="small" @click="handleLogout">退出</a-button>
      </div>
    </div>
    
    <a-table
      :columns="columns"
      :data-source="knowledgeBases"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'visibility'">
          <a-tag :color="record.visibility === 'shared' ? 'green' : 'default'">
            {{ record.visibility === 'shared' ? '共享' : '个人' }}
          </a-tag>
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
              type="link"
              size="small"
              @click="handleViewDetailPage(record)"
            >
              详情页
            </a-button>
            <a-button
              v-if="isOwner(record)"
              type="link"
              size="small"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-button
              v-if="!isMember(record) && record.visibility === 'shared'"
              type="link"
              size="small"
              @click="handleJoin(record)"
            >
              加入
            </a-button>
            <a-button
              v-if="isMember(record) && !isOwner(record)"
              type="link"
              size="small"
              danger
              @click="handleLeave(record)"
            >
              退出
            </a-button>
            <a-button
              v-if="isOwner(record)"
              type="link"
              size="small"
              danger
              @click="handleDelete(record)"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
    
    <!-- 创建/编辑知识库Modal -->
    <a-modal
      v-model:open="editModalVisible"
      :title="editingKb ? '编辑知识库' : '创建知识库'"
      @ok="handleSave"
      @cancel="handleCancelEdit"
    >
      <a-form
        :model="formData"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <a-form-item label="知识库名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入知识库名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea
            v-model:value="formData.description"
            placeholder="请输入知识库描述"
            :rows="3"
          />
        </a-form-item>
        <a-form-item label="可见性">
          <a-radio-group v-model:value="formData.visibility">
            <a-radio value="private">个人</a-radio>
            <a-radio value="shared">共享</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- 知识库详情Modal -->
    <a-modal
      v-model:open="detailModalVisible"
      title="知识库详情"
      width="800px"
      :footer="null"
    >
      <div v-if="selectedKb">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="知识库名称">{{ selectedKb.name }}</a-descriptions-item>
          <a-descriptions-item label="创建者">{{ selectedKb.creator_name }}</a-descriptions-item>
          <a-descriptions-item label="可见性">
            <a-tag :color="selectedKb.visibility === 'shared' ? 'green' : 'default'">
              {{ selectedKb.visibility === 'shared' ? '共享' : '个人' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="成员数量">{{ selectedKb.member_count }}</a-descriptions-item>
          <a-descriptions-item label="文档数量">{{ selectedKb.document_count }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(selectedKb.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">
            {{ selectedKb.description || '无' }}
          </a-descriptions-item>
        </a-descriptions>
        
        <a-divider>成员管理</a-divider>
        
        <div style="margin-bottom: 16px">
          <a-button
            v-if="isOwner(selectedKb)"
            type="primary"
            @click="handleAddMember"
          >
            <template #icon><PlusOutlined /></template>
            添加成员
          </a-button>
        </div>
        
        <a-table
          :columns="memberColumns"
          :data-source="members"
          :loading="membersLoading"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'role'">
              <a-tag :color="getRoleColor(record.role)">
                {{ getRoleText(record.role) }}
              </a-tag>
            </template>
            <template v-if="column.key === 'joined_at'">
              {{ formatDateTime(record.joined_at) }}
            </template>
            <template v-if="column.key === 'action'">
              <a-button
                v-if="isOwner(selectedKb) && record.role !== 'owner'"
                type="link"
                size="small"
                danger
                @click="handleRemoveMember(record)"
              >
                移除
              </a-button>
            </template>
          </template>
        </a-table>
      </div>
    </a-modal>
    
    <!-- 添加成员Modal -->
    <a-modal
      v-model:open="addMemberModalVisible"
      title="添加成员"
      @ok="handleSaveMember"
      @cancel="handleCancelAddMember"
    >
      <a-form
        :model="memberFormData"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <a-form-item label="成员名称" required>
          <a-input v-model:value="memberFormData.member_name" placeholder="请输入成员名称" />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="memberFormData.role">
            <a-select-option value="viewer">查看者</a-select-option>
            <a-select-option value="editor">编辑者</a-select-option>
            <a-select-option value="admin">管理员</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  PlusOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
import {
  getKnowledgeBases,
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
  getMembers,
  addMember,
  removeMember,
  joinKnowledgeBase,
  leaveKnowledgeBase
} from '@/api/knowledgeBase'
import { getUser, removeToken } from '@/utils/auth'

const loading = ref(false)
const knowledgeBases = ref([])
const filterType = ref('my_created')
const currentUser = ref(getUser())
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '知识库名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '可见性', key: 'visibility', width: 100 },
  { title: '创建者', dataIndex: 'creator_name', key: 'creator_name', width: 120 },
  { title: '成员数', dataIndex: 'member_count', key: 'member_count', width: 100 },
  { title: '文档数', dataIndex: 'document_count', key: 'document_count', width: 100 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

// 编辑相关
const editModalVisible = ref(false)
const editingKb = ref(null)
const formData = reactive({
  name: '',
  description: '',
  visibility: 'private'
})

// 详情相关
const detailModalVisible = ref(false)
const selectedKb = ref(null)
const members = ref([])
const membersLoading = ref(false)
const memberColumns = [
  { title: '成员名称', dataIndex: 'member_name', key: 'member_name' },
  { title: '角色', key: 'role', width: 120 },
  { title: '加入时间', key: 'joined_at', width: 180 },
  { title: '操作', key: 'action', width: 100 }
]

// 添加成员相关
const addMemberModalVisible = ref(false)
const memberFormData = reactive({
  member_name: '',
  role: 'viewer'
})

// 加载知识库列表
const loadKnowledgeBases = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    
    if (filterType.value) {
      params.filter_type = filterType.value
    }
    
    const res = await getKnowledgeBases(params)
    knowledgeBases.value = res.knowledge_bases || []
    pagination.total = res.total || 0
  } catch (error) {
    message.error('加载知识库列表失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 表格变化
const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadKnowledgeBases()
}

// 创建知识库
const handleCreate = () => {
  editingKb.value = null
  formData.name = ''
  formData.description = ''
  formData.visibility = 'private'
  editModalVisible.value = true
}

// 编辑知识库
const handleEdit = (record) => {
  editingKb.value = record
  formData.name = record.name
  formData.description = record.description || ''
  formData.visibility = record.visibility
  editModalVisible.value = true
}

// 保存知识库
const handleSave = async () => {
  if (!formData.name.trim()) {
    message.warning('请输入知识库名称')
    return
  }
  
  try {
    if (editingKb.value) {
      // 更新
      await updateKnowledgeBase(editingKb.value.id, formData)
      message.success('更新成功')
    } else {
      // 创建
      await createKnowledgeBase({
        name: formData.name,
        description: formData.description,
        visibility: formData.visibility
      })
      message.success('创建成功')
    }
    editModalVisible.value = false
    loadKnowledgeBases()
  } catch (error) {
    message.error((editingKb.value ? '更新' : '创建') + '失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 取消编辑
const handleCancelEdit = () => {
  editModalVisible.value = false
  editingKb.value = null
}

// 删除知识库
const handleDelete = (record) => {
  const modal = message.confirm({
    title: '确认删除',
    content: `确定要删除知识库"${record.name}"吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await deleteKnowledgeBase(record.id)
        message.success('删除成功')
        modal.destroy()
        loadKnowledgeBases()
      } catch (error) {
        message.error('删除失败: ' + (error.response?.data?.detail || error.message))
        modal.destroy()
      }
    }
  })
}

// 查看详情
const handleViewDetail = async (record) => {
  selectedKb.value = record
  detailModalVisible.value = true
  await loadMembers(record.id)
}

// 查看详情页（带左侧导航）
const handleViewDetailPage = (record) => {
  router.push({ name: 'knowledge-base-detail', params: { id: record.id } })
}

// 加载成员列表
const loadMembers = async (kbId) => {
  membersLoading.value = true
  try {
    const res = await getMembers(kbId)
    members.value = res.members || []
  } catch (error) {
    message.error('加载成员列表失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    membersLoading.value = false
  }
}

// 添加成员
const handleAddMember = () => {
  memberFormData.member_name = ''
  memberFormData.role = 'viewer'
  addMemberModalVisible.value = true
}

// 保存成员
const handleSaveMember = async () => {
  if (!memberFormData.member_name.trim()) {
    message.warning('请输入成员名称')
    return
  }
  
  try {
    await addMember(selectedKb.value.id, memberFormData)
    message.success('添加成员成功')
    addMemberModalVisible.value = false
    await loadMembers(selectedKb.value.id)
    loadKnowledgeBases() // 刷新列表以更新成员数
  } catch (error) {
    message.error('添加成员失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 取消添加成员
const handleCancelAddMember = () => {
  addMemberModalVisible.value = false
}

// 移除成员
const handleRemoveMember = (member) => {
  const modal = message.confirm({
    title: '确认移除',
    content: `确定要移除成员"${member.member_name}"吗？`,
    onOk: async () => {
      try {
        await removeMember(selectedKb.value.id, member.member_name)
        message.success('移除成员成功')
        modal.destroy()
        await loadMembers(selectedKb.value.id)
        loadKnowledgeBases() // 刷新列表以更新成员数
      } catch (error) {
        message.error('移除成员失败: ' + (error.response?.data?.detail || error.message))
        modal.destroy()
      }
    }
  })
}

// 加入知识库
const handleJoin = async (record) => {
  try {
    await joinKnowledgeBase(record.id)
    message.success('加入成功')
    loadKnowledgeBases()
  } catch (error) {
    message.error('加入失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 退出知识库
const handleLeave = async (record) => {
  try {
    await leaveKnowledgeBase(record.id)
    message.success('退出成功')
    loadKnowledgeBases()
  } catch (error) {
    message.error('退出失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 判断是否为创建者
const isOwner = (record) => {
  return currentUser.value && record.creator_name === currentUser.value.username
}

// 判断是否为成员
const isMember = (record) => {
  // 使用后端返回的 is_member 字段
  return record.is_member === true
}

// 退出登录
const handleLogout = () => {
  removeToken()
  // 清除当前用户信息
  currentUser.value = null
  // 跳转到登录页
  router.push('/login')
}

// 格式化日期时间
const formatDateTime = (dateTimeStr) => {
  if (!dateTimeStr) return '-'
  const date = new Date(dateTimeStr)
  return date.toLocaleString('zh-CN')
}

// 获取角色文本
const getRoleText = (role) => {
  const roleMap = {
    owner: '创建者',
    admin: '管理员',
    editor: '编辑者',
    viewer: '查看者'
  }
  return roleMap[role] || role
}

// 获取角色颜色
const getRoleColor = (role) => {
  const colorMap = {
    owner: 'red',
    admin: 'orange',
    editor: 'blue',
    viewer: 'default'
  }
  return colorMap[role] || 'default'
}

onMounted(() => {
  loadKnowledgeBases()
})
</script>

<style scoped>
</style>

