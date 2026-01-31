<template>
  <a-card>
    <template #title>
      <span>用户管理</span>
    </template>
    
    <!-- 工具栏 -->
    <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
      <a-button type="primary" @click="handleCreate">
        <template #icon><PlusOutlined /></template>
        创建用户
      </a-button>
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索用户名或邮箱"
        style="width: 300px"
        @search="loadUsers"
        allow-clear
        @clear="loadUsers"
      />
      <a-button @click="loadUsers" :loading="loading">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>
    
    <!-- 用户列表 -->
    <a-table
      :columns="columns"
      :data-source="users"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'role'">
          <a-tag :color="getRoleColor(record.role)">
            {{ getRoleText(record.role) }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '激活' : '禁用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
            <a-button type="link" size="small" @click="handleResetPassword(record)">重置密码</a-button>
            <a-button 
              type="link" 
              size="small" 
              danger 
              :disabled="record.id === currentUserId"
              @click="handleDelete(record)"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
    
    <!-- 创建/编辑用户模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingUser ? '编辑用户' : '创建用户'"
      :confirm-loading="saving"
      @ok="handleSave"
      @cancel="handleCancel"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <a-form-item label="用户名" name="username" required>
          <a-input 
            v-model:value="formData.username" 
            placeholder="请输入用户名"
            :disabled="!!editingUser"
          />
        </a-form-item>
        <a-form-item v-if="!editingUser" label="密码" name="password" required>
          <a-input-password 
            v-model:value="formData.password" 
            placeholder="请输入密码（最长72字节）"
            :maxlength="72"
          />
        </a-form-item>
        <a-form-item label="邮箱" name="email">
          <a-input 
            v-model:value="formData.email" 
            placeholder="请输入邮箱（可选）"
          />
        </a-form-item>
        <a-form-item label="角色" name="role" required>
          <a-select v-model:value="formData.role" placeholder="请选择角色">
            <a-select-option value="admin">Admin（管理员）</a-select-option>
            <a-select-option value="manage">Manage（管理）</a-select-option>
            <a-select-option value="common">Common（普通用户）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态" name="is_active">
          <a-switch v-model:checked="formData.is_active" checked-children="激活" un-checked-children="禁用" />
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- 重置密码模态框 -->
    <a-modal
      v-model:open="resetPasswordModalVisible"
      title="重置密码"
      :confirm-loading="resettingPassword"
      @ok="handleResetPasswordConfirm"
      @cancel="handleResetPasswordCancel"
    >
      <a-form
        ref="resetPasswordFormRef"
        :model="resetPasswordForm"
        :rules="resetPasswordRules"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <a-form-item label="用户名">
          <a-input :value="resetPasswordUser?.username" disabled />
        </a-form-item>
        <a-form-item label="新密码" name="new_password" required>
          <a-input-password 
            v-model:value="resetPasswordForm.new_password" 
            placeholder="请输入新密码（最长72字节）"
            :maxlength="72"
          />
        </a-form-item>
        <a-form-item label="确认密码" name="confirm_password" required>
          <a-input-password 
            v-model:value="resetPasswordForm.confirm_password" 
            placeholder="请再次输入新密码"
            :maxlength="72"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, resetPassword } from '@/api/userManagement'
import { getUser } from '@/utils/auth'

const loading = ref(false)
const users = ref([])
const searchKeyword = ref('')
const modalVisible = ref(false)
const editingUser = ref(null)
const saving = ref(false)
const resetPasswordModalVisible = ref(false)
const resettingPassword = ref(false)
const resetPasswordUser = ref(null)
const formRef = ref(null)
const resetPasswordFormRef = ref(null)

const currentUser = ref(getUser())
const currentUserId = computed(() => currentUser.value?.id)

const formData = reactive({
  username: '',
  password: '',
  email: '',
  role: 'common',
  is_active: true
})

const resetPasswordForm = reactive({
  new_password: '',
  confirm_password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度应在3-50个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

const resetPasswordRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value) => {
        if (value !== resetPasswordForm.new_password) {
          return Promise.reject('两次输入的密码不一致')
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ]
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用户名', dataIndex: 'username', key: 'username', width: 150 },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 200 },
  { title: '角色', key: 'role', width: 120 },
  { title: '状态', key: 'is_active', width: 100 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 250, fixed: 'right' }
]

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const getRoleColor = (role) => {
  const colors = {
    admin: 'red',
    manage: 'orange',
    common: 'blue'
  }
  return colors[role] || 'default'
}

const getRoleText = (role) => {
  const texts = {
    admin: '管理员',
    manage: '管理',
    common: '普通用户'
  }
  return texts[role] || role
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      keyword: searchKeyword.value || undefined
    }
    const res = await getUsers(params)
    users.value = res.users || []
    pagination.total = res.total || 0
  } catch (error) {
    message.error('加载用户列表失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 表格变化处理
const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadUsers()
}

// 创建用户
const handleCreate = () => {
  editingUser.value = null
  Object.assign(formData, {
    username: '',
    password: '',
    email: '',
    role: 'common',
    is_active: true
  })
  modalVisible.value = true
}

// 编辑用户
const handleEdit = (record) => {
  editingUser.value = record
  Object.assign(formData, {
    username: record.username,
    password: '',
    email: record.email || '',
    role: record.role || 'common',
    is_active: record.is_active !== false
  })
  modalVisible.value = true
}

// 保存用户
const handleSave = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    
    if (editingUser.value) {
      // 更新用户
      const updateData = {
        username: formData.username,
        email: formData.email || undefined,
        role: formData.role,
        is_active: formData.is_active
      }
      await updateUser(editingUser.value.id, updateData)
      message.success('用户更新成功')
    } else {
      // 创建用户 - 只发送需要的字段
      const createData = {
        username: formData.username,
        password: formData.password,
        email: formData.email || undefined,
        role: formData.role,
        is_active: formData.is_active
      }
      await createUser(createData)
      message.success('用户创建成功')
    }
    
    modalVisible.value = false
    loadUsers()
  } catch (error) {
    if (error.errorFields) {
      // 表单验证错误
      return
    }
    // 处理API错误响应
    let errorMsg = '未知错误'
    if (error.response?.data?.detail) {
      // FastAPI返回的详细错误信息
      if (Array.isArray(error.response.data.detail)) {
        // 验证错误列表
        errorMsg = error.response.data.detail.map(err => `${err.loc?.join('.')}: ${err.msg}`).join('; ')
      } else {
        // 字符串错误信息
        errorMsg = error.response.data.detail
      }
    } else if (error.message) {
      errorMsg = error.message
    }
    message.error((editingUser.value ? '更新' : '创建') + '用户失败: ' + errorMsg)
  } finally {
    saving.value = false
  }
}

// 取消
const handleCancel = () => {
  modalVisible.value = false
  editingUser.value = null
  formRef.value?.resetFields()
}

// 删除用户
const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除用户 "${record.username}" 吗？此操作不可恢复。`,
    okText: '确定',
    cancelText: '取消',
    okType: 'danger',
    onOk: async () => {
      try {
        await deleteUser(record.id)
        message.success('用户删除成功')
        loadUsers()
      } catch (error) {
        message.error('删除用户失败: ' + (error.message || '未知错误'))
      }
    }
  })
}

// 重置密码
const handleResetPassword = (record) => {
  resetPasswordUser.value = record
  resetPasswordForm.new_password = ''
  resetPasswordForm.confirm_password = ''
  resetPasswordModalVisible.value = true
}

// 确认重置密码
const handleResetPasswordConfirm = async () => {
  try {
    await resetPasswordFormRef.value.validate()
    resettingPassword.value = true
    
    await resetPassword(resetPasswordUser.value.id, resetPasswordForm.new_password)
    message.success('密码重置成功')
    resetPasswordModalVisible.value = false
  } catch (error) {
    if (error.errorFields) {
      // 表单验证错误
      return
    }
    message.error('重置密码失败: ' + (error.message || '未知错误'))
  } finally {
    resettingPassword.value = false
  }
}

// 取消重置密码
const handleResetPasswordCancel = () => {
  resetPasswordModalVisible.value = false
  resetPasswordUser.value = null
  resetPasswordFormRef.value?.resetFields()
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
</style>

