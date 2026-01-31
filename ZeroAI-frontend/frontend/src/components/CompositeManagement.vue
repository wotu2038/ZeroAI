<template>
  <div class="composite-management">
    <a-card title="组合管理">
      <template #extra>
        <a-button type="primary" @click="handleCreate">
          <template #icon><PlusOutlined /></template>
          创建新组合
        </a-button>
      </template>

      <a-space direction="vertical" style="width: 100%" size="large">
        <!-- 筛选器 -->
        <a-space>
          <span>组合类型：</span>
          <a-select
            v-model:value="filterType"
            placeholder="全部类型"
            style="width: 150px"
            allow-clear
            @change="loadComposites"
          >
            <a-select-option value="">全部类型</a-select-option>
            <a-select-option value="project">项目</a-select-option>
            <a-select-option value="feature">功能</a-select-option>
            <a-select-option value="document">文档</a-select-option>
            <a-select-option value="custom">自定义</a-select-option>
          </a-select>
          <a-button @click="loadComposites" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </a-space>

        <!-- 组合列表 -->
        <a-list
          :data-source="composites"
          :loading="loading"
          :pagination="pagination"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <a-space>
                    <span style="font-size: 16px; font-weight: 500">{{ item.name }}</span>
                    <a-tag :color="getTypeColor(item.type)">{{ getTypeLabel(item.type) }}</a-tag>
                  </a-space>
                </template>
                <template #description>
                  <div style="margin-top: 8px">
                    <div v-if="item.description" style="margin-bottom: 8px; color: #666">
                      {{ item.description }}
                    </div>
                    <div>
                      <span style="color: #999">包含GroupID：</span>
                      <a-tag
                        v-for="groupId in item.group_ids"
                        :key="groupId"
                        style="margin-right: 4px"
                      >
                        {{ groupId }}
                      </a-tag>
                      <span v-if="item.group_ids.length === 0" style="color: #999">无</span>
                    </div>
                    <div style="margin-top: 4px; color: #999; font-size: 12px">
                      创建时间：{{ formatDate(item.created_at) }}
                    </div>
                  </div>
                </template>
              </a-list-item-meta>
              <template #actions>
                <a-button type="link" @click="handleQueryGraph(item)">
                  <template #icon><SearchOutlined /></template>
                  查询图谱
                </a-button>
                <a-button type="link" @click="handleEdit(item)">
                  <template #icon><EditOutlined /></template>
                  编辑
                </a-button>
                <a-popconfirm
                  title="确定要删除这个组合吗？"
                  @confirm="handleDelete(item)"
                >
                  <a-button type="link" danger>
                    <template #icon><DeleteOutlined /></template>
                    删除
                  </a-button>
                </a-popconfirm>
              </template>
            </a-list-item>
          </template>
          <template #empty>
            <a-empty description="暂无组合，点击上方按钮创建" />
          </template>
        </a-list>
      </a-space>
    </a-card>

    <!-- 创建/编辑表单 -->
    <CompositeForm
      v-model:open="formVisible"
      :composite="currentComposite"
      @success="handleFormSuccess"
    />

    <!-- 组合图谱查询（使用GraphSearch组件） -->
    <a-drawer
      v-model:open="graphDrawerVisible"
      title="组合图谱查询"
      width="90%"
      placement="right"
    >
      <GraphSearch
        v-if="graphDrawerVisible"
        :composite-uuid="selectedCompositeUuid"
        :group-ids="selectedGroupIds"
        mode="composite"
      />
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import {
  getCompositeList,
  deleteComposite,
  createComposite,
  updateComposite
} from '../api/composite'
import CompositeForm from './CompositeForm.vue'
import GraphSearch from './GraphSearch.vue'

const loading = ref(false)
const filterType = ref('')
const composites = ref([])
const formVisible = ref(false)
const currentComposite = ref(null)
const graphDrawerVisible = ref(false)
const selectedCompositeUuid = ref(null)
const selectedGroupIds = ref([])

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 条`
})

const loadComposites = async () => {
  loading.value = true
  try {
    const response = await getCompositeList(filterType.value || null)
    if (response) {
      composites.value = response
      pagination.total = response.length
    }
  } catch (error) {
    console.error('加载组合列表失败:', error)
    message.error(`加载失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  currentComposite.value = null
  formVisible.value = true
}

const handleEdit = (composite) => {
  currentComposite.value = composite
  formVisible.value = true
}

const handleDelete = async (composite) => {
  try {
    await deleteComposite(composite.uuid)
    message.success('删除成功')
    loadComposites()
  } catch (error) {
    console.error('删除失败:', error)
    message.error(`删除失败: ${error.message || error}`)
  }
}

const handleQueryGraph = (composite) => {
  selectedCompositeUuid.value = composite.uuid
  selectedGroupIds.value = composite.group_ids || []
  graphDrawerVisible.value = true
}

const handleFormSuccess = async (result) => {
  try {
    if (result.action === 'create') {
      await createComposite(result.data)
      message.success('创建成功')
    } else if (result.action === 'update') {
      await updateComposite(result.uuid, result.data)
      message.success('更新成功')
    }
    formVisible.value = false
    currentComposite.value = null
    loadComposites()
  } catch (error) {
    console.error('操作失败:', error)
    message.error(`操作失败: ${error.message || error}`)
    throw error
  }
}

const getTypeColor = (type) => {
  const colorMap = {
    project: 'blue',
    feature: 'green',
    document: 'orange',
    custom: 'purple'
  }
  return colorMap[type] || 'default'
}

const getTypeLabel = (type) => {
  const labelMap = {
    project: '项目',
    feature: '功能',
    document: '文档',
    custom: '自定义'
  }
  return labelMap[type] || type
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadComposites()
})
</script>

<style scoped>
.composite-management {
  padding: 16px;
}
</style>

