<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑组合' : '创建组合'"
    width="800px"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="loading"
  >
    <a-form
      :model="formData"
      :label-col="{ span: 6 }"
      :wrapper-col="{ span: 18 }"
      ref="formRef"
    >
      <a-form-item
        label="组合名称"
        name="name"
        :rules="[{ required: true, message: '请输入组合名称' }]"
      >
        <a-input v-model:value="formData.name" placeholder="请输入组合名称" />
      </a-form-item>

      <a-form-item
        label="组合类型"
        name="type"
        :rules="[{ required: true, message: '请选择组合类型' }]"
      >
        <a-select v-model:value="formData.type" placeholder="请选择组合类型">
          <a-select-option value="project">项目</a-select-option>
          <a-select-option value="feature">功能</a-select-option>
          <a-select-option value="document">文档</a-select-option>
          <a-select-option value="custom">自定义</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea
          v-model:value="formData.description"
          placeholder="请输入描述信息（可选）"
          :rows="3"
        />
      </a-form-item>

      <a-form-item
        label="选择GroupID"
        name="group_ids"
        :rules="[{ required: true, message: '请至少选择一个GroupID' }]"
      >
        <a-space direction="vertical" style="width: 100%">
          <a-select
            v-model:value="formData.group_ids"
            mode="multiple"
            placeholder="选择或输入多个GroupID"
            style="width: 100%"
            :loading="loadingDocuments"
            :filter-option="false"
            @search="handleGroupIdSearch"
            show-search
            allow-clear
          >
            <a-select-option
              v-for="doc in documentOptions"
              :key="doc.document_id"
              :value="doc.document_id"
            >
              {{ doc.document_name }} ({{ doc.document_id }})
            </a-select-option>
          </a-select>
          <div v-if="formData.group_ids.length > 0" style="margin-top: 8px">
            <a-tag
              v-for="groupId in formData.group_ids"
              :key="groupId"
              closable
              @close="removeGroupId(groupId)"
              style="margin-bottom: 4px"
            >
              {{ groupId }}
            </a-tag>
          </div>
        </a-space>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getDocumentList } from '../api/wordDocument'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  composite: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:open', 'success'])

const visible = ref(false)
const loading = ref(false)
const loadingDocuments = ref(false)
const formRef = ref(null)
const documentOptions = ref([])

const formData = reactive({
  name: '',
  type: 'project',
  description: '',
  group_ids: []
})

const isEdit = computed(() => !!props.composite)

watch(() => props.open, (val) => {
  visible.value = val
  if (val) {
    if (props.composite) {
      // 编辑模式：填充表单数据
      formData.name = props.composite.name || ''
      formData.type = props.composite.type || 'project'
      formData.description = props.composite.description || ''
      formData.group_ids = [...(props.composite.group_ids || [])]
    } else {
      // 创建模式：重置表单
      formData.name = ''
      formData.type = 'project'
      formData.description = ''
      formData.group_ids = []
    }
  }
})

watch(visible, (val) => {
  emit('update:open', val)
})

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentList('qianwen', 100, 0)
    if (response && response.documents) {
      // 去重：只保留每个 group_id 的一个版本（选择最新的）
      const groupIdMap = new Map()
      response.documents.forEach(doc => {
        const groupId = doc.document_id
        if (!groupIdMap.has(groupId) || 
            (doc.statistics?.version_number || 0) > (groupIdMap.get(groupId).statistics?.version_number || 0)) {
          groupIdMap.set(groupId, doc)
        }
      })
      documentOptions.value = Array.from(groupIdMap.values())
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error('加载文档列表失败')
  } finally {
    loadingDocuments.value = false
  }
}

const handleGroupIdSearch = (value) => {
  // 允许用户输入自定义GroupID
}

const removeGroupId = (groupId) => {
  const index = formData.group_ids.indexOf(groupId)
  if (index > -1) {
    formData.group_ids.splice(index, 1)
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    if (formData.group_ids.length === 0) {
      message.warning('请至少选择一个GroupID')
      return
    }

    loading.value = true
    
    const submitData = {
      name: formData.name,
      type: formData.type,
      description: formData.description || undefined,
      group_ids: formData.group_ids
    }

    if (isEdit.value) {
      // 编辑模式：调用更新API
      await emit('success', {
        action: 'update',
        uuid: props.composite.uuid,
        data: submitData
      })
    } else {
      // 创建模式：调用创建API
      await emit('success', {
        action: 'create',
        data: submitData
      })
    }

    visible.value = false
    message.success(isEdit.value ? '更新成功' : '创建成功')
  } catch (error) {
    if (error.errorFields) {
      // 表单验证错误
      return
    }
    console.error('提交失败:', error)
    message.error(`提交失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  visible.value = false
}

onMounted(() => {
  loadDocuments()
})
</script>

<script>
import { computed } from 'vue'
</script>

<style scoped>
</style>

