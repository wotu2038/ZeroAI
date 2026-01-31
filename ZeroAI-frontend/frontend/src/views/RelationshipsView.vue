<template>
  <a-card>
    <template #title>
      <a-space>
        <span>关系管理</span>
        <a-button type="primary" @click="showCreateModal">
          <template #icon><PlusOutlined /></template>
          新建关系
        </a-button>
      </a-space>
    </template>

    <a-space style="margin-bottom: 16px">
      <a-select
        v-model:value="filterType"
        placeholder="筛选类型"
        style="width: 150px"
        allow-clear
        @change="loadRelationships"
      >
        <a-select-option v-for="type in relationshipTypes" :key="type" :value="type">
          {{ type }}
        </a-select-option>
      </a-select>
    </a-space>

    <a-table
      :columns="columns"
      :data-source="relationships"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'type'">
          <a-tag color="blue">{{ record.type }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
            <a-button type="link" size="small" danger @click="handleDelete(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 创建/编辑关系模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingRelationship ? '编辑关系' : '新建关系'"
      @ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form :model="formData" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="源实体" required>
          <a-input v-model:value="formData.source" placeholder="实体名称或ID" />
        </a-form-item>
        <a-form-item label="目标实体" required>
          <a-input v-model:value="formData.target" placeholder="实体名称或ID" />
        </a-form-item>
        <a-form-item label="关系类型" required>
          <a-select v-model:value="formData.type">
            <a-select-option v-for="type in relationshipTypes" :key="type" :value="type">
              {{ type }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="属性">
          <a-textarea
            v-model:value="propertiesText"
            placeholder='JSON格式，例如: {"since": "2020"}'
            :rows="4"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import {
  getRelationships,
  createRelationship,
  updateRelationship,
  deleteRelationship,
  getRelationshipTypes
} from '../api/relationships'

const relationships = ref([])
const loading = ref(false)
const filterType = ref(null)
const relationshipTypes = ref([])
const modalVisible = ref(false)
const editingRelationship = ref(null)
const formData = ref({
  source: '',
  target: '',
  type: 'RELATED_TO',
  properties: {}
})
const propertiesText = ref('')

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
  { title: '源实体', dataIndex: 'source', key: 'source' },
  { title: '关系类型', key: 'type', width: 150 },
  { title: '目标实体', dataIndex: 'target', key: 'target' },
  { title: '属性', key: 'properties', customRender: ({ record }) => JSON.stringify(record.properties) },
  { title: '操作', key: 'action', width: 150 }
]

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`
})

const loadRelationships = async () => {
  loading.value = true
  try {
    const params = {
      type: filterType.value || undefined,
      limit: pagination.value.pageSize,
      skip: (pagination.value.current - 1) * pagination.value.pageSize
    }
    const data = await getRelationships(params)
    relationships.value = data
    pagination.value.total = data.length
  } catch (error) {
    message.error('加载关系失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadRelationships()
}

const showCreateModal = () => {
  editingRelationship.value = null
  formData.value = { source: '', target: '', type: 'RELATED_TO', properties: {} }
  propertiesText.value = ''
  modalVisible.value = true
}

const handleEdit = (record) => {
  editingRelationship.value = record
  formData.value = {
    source: record.source,
    target: record.target,
    type: record.type,
    properties: record.properties
  }
  propertiesText.value = JSON.stringify(record.properties, null, 2)
  modalVisible.value = true
}

const handleSubmit = async () => {
  if (!formData.value.source || !formData.value.target || !formData.value.type) {
    message.warning('请填写完整信息')
    return
  }

  try {
    if (propertiesText.value) {
      try {
        formData.value.properties = JSON.parse(propertiesText.value)
      } catch (e) {
        message.error('属性格式错误，请输入有效的JSON')
        return
      }
    }

    if (editingRelationship.value) {
      await updateRelationship(editingRelationship.value.id, formData.value)
      message.success('更新成功')
    } else {
      await createRelationship(formData.value)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadRelationships()
  } catch (error) {
    message.error('操作失败: ' + error.message)
  }
}

const handleCancel = () => {
  modalVisible.value = false
  editingRelationship.value = null
  formData.value = { source: '', target: '', type: 'RELATED_TO', properties: {} }
  propertiesText.value = ''
}

const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除这条关系吗？`,
    onOk: async () => {
      try {
        await deleteRelationship(record.id)
        message.success('删除成功')
        loadRelationships()
      } catch (error) {
        message.error('删除失败: ' + error.message)
      }
    }
  })
}

const loadRelationshipTypes = async () => {
  try {
    relationshipTypes.value = await getRelationshipTypes()
  } catch (error) {
    console.error('加载关系类型失败:', error)
  }
}

onMounted(() => {
  loadRelationshipTypes()
  loadRelationships()
})
</script>

