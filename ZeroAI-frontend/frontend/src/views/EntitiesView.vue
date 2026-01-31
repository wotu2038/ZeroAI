<template>
  <a-card>
    <template #title>
      <a-space>
        <span>实体管理</span>
        <a-button type="primary" @click="showCreateModal">
          <template #icon><PlusOutlined /></template>
          新建实体
        </a-button>
      </a-space>
    </template>

    <a-space style="margin-bottom: 16px">
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索实体"
        style="width: 300px"
        @search="handleSearch"
      />
      <a-select
        v-model:value="filterType"
        placeholder="筛选类型"
        style="width: 150px"
        allow-clear
        @change="loadEntities"
      >
        <a-select-option v-for="type in entityTypes" :key="type" :value="type">
          {{ type }}
        </a-select-option>
      </a-select>
    </a-space>

    <a-table
      :columns="columns"
      :data-source="entities"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'type'">
          <a-tag :color="getTypeColor(record.type)">{{ record.type }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
            <a-button type="link" size="small" danger @click="handleDelete(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 创建/编辑实体模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingEntity ? '编辑实体' : '新建实体'"
      @ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form :model="formData" :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="名称" required>
          <a-input v-model:value="formData.name" />
        </a-form-item>
        <a-form-item label="类型" required>
          <a-select v-model:value="formData.type">
            <a-select-option v-for="type in entityTypes" :key="type" :value="type">
              {{ type }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="属性">
          <a-textarea
            v-model:value="propertiesText"
            placeholder='JSON格式，例如: {"age": 30, "city": "北京"}'
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
import { getEntities, createEntity, updateEntity, deleteEntity, searchEntities, getEntityTypes } from '../api/entities'

const entities = ref([])
const loading = ref(false)
const searchKeyword = ref('')
const filterType = ref(null)
const entityTypes = ref([])
const modalVisible = ref(false)
const editingEntity = ref(null)
const formData = ref({
  name: '',
  type: 'Concept',
  properties: {}
})
const propertiesText = ref('')

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', key: 'type', width: 150 },
  { title: '属性', key: 'properties', customRender: ({ record }) => JSON.stringify(record.properties) },
  { title: '操作', key: 'action', width: 150 }
]

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`
})

const getTypeColor = (type) => {
  const colors = {
    Person: 'blue',
    Organization: 'green',
    Location: 'orange',
    Concept: 'purple',
    Event: 'pink'
  }
  return colors[type] || 'default'
}

const loadEntities = async () => {
  loading.value = true
  try {
    const params = {
      type: filterType.value || undefined,
      limit: pagination.value.pageSize,
      skip: (pagination.value.current - 1) * pagination.value.pageSize
    }
    const data = await getEntities(params)
    entities.value = data
    // 注意：实际API应该返回总数，这里简化处理
    pagination.value.total = data.length
  } catch (error) {
    message.error('加载实体失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  if (!searchKeyword.value) {
    loadEntities()
    return
  }
  loading.value = true
  try {
    const data = await searchEntities(searchKeyword.value)
    entities.value = data
    pagination.value.total = data.length
  } catch (error) {
    message.error('搜索失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadEntities()
}

const showCreateModal = () => {
  editingEntity.value = null
  formData.value = { name: '', type: 'Concept', properties: {} }
  propertiesText.value = ''
  modalVisible.value = true
}

const handleEdit = (record) => {
  editingEntity.value = record
  formData.value = {
    name: record.name,
    type: record.type,
    properties: record.properties
  }
  propertiesText.value = JSON.stringify(record.properties, null, 2)
  modalVisible.value = true
}

const handleSubmit = async () => {
  if (!formData.value.name || !formData.value.type) {
    message.warning('请填写名称和类型')
    return
  }

  try {
    // 解析属性
    if (propertiesText.value) {
      try {
        formData.value.properties = JSON.parse(propertiesText.value)
      } catch (e) {
        message.error('属性格式错误，请输入有效的JSON')
        return
      }
    }

    if (editingEntity.value) {
      await updateEntity(editingEntity.value.id, formData.value)
      message.success('更新成功')
    } else {
      await createEntity(formData.value)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadEntities()
  } catch (error) {
    message.error('操作失败: ' + error.message)
  }
}

const handleCancel = () => {
  modalVisible.value = false
  editingEntity.value = null
  formData.value = { name: '', type: 'Concept', properties: {} }
  propertiesText.value = ''
}

const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除实体 "${record.name}" 吗？`,
    onOk: async () => {
      try {
        await deleteEntity(record.id)
        message.success('删除成功')
        loadEntities()
      } catch (error) {
        message.error('删除失败: ' + error.message)
      }
    }
  })
}

const loadEntityTypes = async () => {
  try {
    entityTypes.value = await getEntityTypes()
  } catch (error) {
    console.error('加载实体类型失败:', error)
  }
}

onMounted(() => {
  loadEntityTypes()
  loadEntities()
})
</script>

