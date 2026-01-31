<template>
  <a-card>
    <template #title>
      <span>模板管理</span>
    </template>
    
    <!-- 工具栏 -->
    <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
      <a-button type="primary" @click="handleCreate">
        <template #icon><PlusOutlined /></template>
        创建模板
      </a-button>
      <a-button type="default" @click="handleGenerate">
        <template #icon><RobotOutlined /></template>
        🤖 自动生成
      </a-button>
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索模板名称或描述"
        style="width: 300px"
        @search="loadTemplates"
        allow-clear
        @clear="loadTemplates"
      />
      <a-select
        v-model:value="filterCategory"
        placeholder="筛选分类"
        style="width: 150px"
        allow-clear
        @change="loadTemplates"
      >
        <a-select-option value="requirement">需求文档</a-select-option>
        <a-select-option value="technical">技术文档</a-select-option>
        <a-select-option value="product">产品文档</a-select-option>
        <a-select-option value="custom">自定义</a-select-option>
      </a-select>
      <a-select
        v-model:value="filterTemplateType"
        placeholder="筛选模板类型"
        style="width: 150px"
        allow-clear
        @change="loadTemplates"
      >
        <a-select-option value="cognify">Cognify</a-select-option>
        <a-select-option value="memify">Memify</a-select-option>
      </a-select>
      <a-button @click="loadTemplates" :loading="loading">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>
    
    <!-- 模板列表 -->
    <a-table
      :columns="columns"
      :data-source="templates"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a-button type="link" @click="handleView(record)">
            {{ record.name }}
          </a-button>
          <a-tag v-if="record.is_default" color="blue" style="margin-left: 8px">默认</a-tag>
          <a-tag v-if="record.is_system" color="orange" style="margin-left: 8px">系统</a-tag>
        </template>
        <template v-else-if="column.key === 'template_type'">
          <a-tag v-if="getTemplateType(record) === 'Cognify'" color="blue">Cognify</a-tag>
          <a-tag v-else-if="getTemplateType(record) === 'Memify'" color="green">Memify</a-tag>
          <a-tag v-else color="default">通用</a-tag>
        </template>
        <template v-else-if="column.key === 'category'">
          <a-tag>{{ getCategoryName(record.category) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'entity_types_count'">
          {{ Object.keys(record.entity_types || {}).length }}
        </template>
        <template v-else-if="column.key === 'edge_types_count'">
          {{ Object.keys(record.edge_types || {}).length }}
        </template>
        <template v-else-if="column.key === 'usage_count'">
          {{ record.usage_count }}
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleView(record)">查看</a-button>
            <a-button 
              type="link" 
              size="small" 
              :disabled="record.is_system"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-button 
              type="link" 
              size="small" 
              danger 
              :disabled="record.is_system || record.is_default"
              @click="handleDelete(record)"
            >
              删除
            </a-button>
            <a-button 
              v-if="!record.is_default" 
              type="link" 
              size="small" 
              @click="handleSetDefault(record)"
            >
              设为默认
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
    
    <!-- 创建/编辑模板模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      width="900px"
      :confirm-loading="saving"
      @ok="handleSave"
      @cancel="handleCancelModal"
    >
      <a-form :model="formData" :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
        <a-form-item label="模板名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入模板名称" />
        </a-form-item>
        <a-form-item label="模板描述">
          <a-textarea v-model:value="formData.description" :rows="2" placeholder="请输入模板描述" />
        </a-form-item>
        <a-form-item label="模板分类">
          <a-select v-model:value="formData.category">
            <a-select-option value="requirement">需求文档</a-select-option>
            <a-select-option value="technical">技术文档</a-select-option>
            <a-select-option value="product">产品文档</a-select-option>
            <a-select-option value="custom">自定义</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="模板配置">
          <a-tabs v-model:activeKey="activeTab">
            <a-tab-pane key="json" tab="JSON编辑">
              <a-textarea
                v-model:value="formDataJson"
                :rows="15"
                placeholder="请输入JSON配置"
                @change="handleJsonChange"
              />
              <a-button @click="handleValidate" style="margin-top: 8px" :loading="validating">校验</a-button>
            </a-tab-pane>
          </a-tabs>
        </a-form-item>
        <a-form-item v-if="validationResult">
          <a-alert
            :type="validationResult.valid ? 'success' : 'error'"
            :message="validationResult.valid ? '校验通过' : '校验失败'"
          >
            <template v-if="validationResult.errors && validationResult.errors.length > 0">
              <div><strong>错误:</strong></div>
              <ul>
                <li v-for="error in validationResult.errors" :key="error">{{ error }}</li>
              </ul>
            </template>
            <template v-if="validationResult.warnings && validationResult.warnings.length > 0">
              <div><strong>警告:</strong></div>
              <ul>
                <li v-for="warning in validationResult.warnings" :key="warning">{{ warning }}</li>
              </ul>
            </template>
          </a-alert>
        </a-form-item>
        <a-form-item label="设为默认">
          <a-switch v-model:checked="formData.is_default" />
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- 模板详情模态框 -->
    <a-modal
      v-model:open="detailVisible"
      title="模板详情"
      width="900px"
      :footer="null"
    >
      <div v-if="currentTemplate">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="模板名称">{{ currentTemplate.name }}</a-descriptions-item>
          <a-descriptions-item label="模板类型">
            <a-tag v-if="getTemplateType(currentTemplate) === 'Cognify'" color="blue">Cognify</a-tag>
            <a-tag v-else-if="getTemplateType(currentTemplate) === 'Memify'" color="green">Memify</a-tag>
            <a-tag v-else color="default">通用</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模板分类">{{ getCategoryName(currentTemplate.category) }}</a-descriptions-item>
          <a-descriptions-item label="模板描述" :span="2">{{ currentTemplate.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="实体类型数量" v-if="getTemplateType(currentTemplate) === 'Cognify'">
            {{ Object.keys(currentTemplate.entity_types || {}).length }}
          </a-descriptions-item>
          <a-descriptions-item label="关系类型数量" v-if="getTemplateType(currentTemplate) === 'Cognify'">
            {{ Object.keys(currentTemplate.edge_types || {}).length }}
          </a-descriptions-item>
          <a-descriptions-item label="使用次数">{{ currentTemplate.usage_count }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(currentTemplate.created_at) }}</a-descriptions-item>
        </a-descriptions>
        
        <!-- Cognify模板显示 -->
        <template v-if="getTemplateType(currentTemplate) === 'Cognify'">
        <a-divider>实体类型</a-divider>
        <a-table
          :columns="entityColumns"
          :data-source="entityTypesList"
          :pagination="false"
          size="small"
        />
        
        <a-divider>关系类型</a-divider>
        <a-table
          :columns="edgeColumns"
          :data-source="edgeTypesList"
          :pagination="false"
          size="small"
        />
        </template>
        
        <!-- Memify模板显示 -->
        <template v-else-if="getTemplateType(currentTemplate) === 'Memify'">
          <a-divider>Extraction配置</a-divider>
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="启用状态">
              <a-tag :color="getMemifyConfig(currentTemplate, 'extraction', 'enabled') ? 'green' : 'red'">
                {{ getMemifyConfig(currentTemplate, 'extraction', 'enabled') ? '已启用' : '已禁用' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="任务类型">
              {{ getMemifyConfig(currentTemplate, 'extraction', 'task') || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="节点类型" v-if="getMemifyConfig(currentTemplate, 'extraction', 'node_types')">
              {{ getMemifyConfig(currentTemplate, 'extraction', 'node_types').join(', ') }}
            </a-descriptions-item>
            <a-descriptions-item label="最大跳数" v-if="getMemifyConfig(currentTemplate, 'extraction', 'max_hops')">
              {{ getMemifyConfig(currentTemplate, 'extraction', 'max_hops') }}
            </a-descriptions-item>
          </a-descriptions>
          
          <a-divider>Enrichment配置</a-divider>
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="启用状态">
              <a-tag :color="getMemifyConfig(currentTemplate, 'enrichment', 'enabled') ? 'green' : 'red'">
                {{ getMemifyConfig(currentTemplate, 'enrichment', 'enabled') ? '已启用' : '已禁用' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="任务类型">
              {{ getMemifyConfig(currentTemplate, 'enrichment', 'task') || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="规则节点集名称" v-if="getMemifyConfig(currentTemplate, 'enrichment', 'rules_nodeset_name')">
              {{ getMemifyConfig(currentTemplate, 'enrichment', 'rules_nodeset_name') }}
            </a-descriptions-item>
            <a-descriptions-item label="用户Prompt文件" v-if="getMemifyConfig(currentTemplate, 'enrichment', 'user_prompt_location')">
              {{ getMemifyConfig(currentTemplate, 'enrichment', 'user_prompt_location') }}
            </a-descriptions-item>
            <a-descriptions-item label="系统Prompt文件" v-if="getMemifyConfig(currentTemplate, 'enrichment', 'system_prompt_location')">
              {{ getMemifyConfig(currentTemplate, 'enrichment', 'system_prompt_location') }}
            </a-descriptions-item>
          </a-descriptions>
        </template>
        
        <a-divider>JSON配置</a-divider>
        <a-tabs v-model:activeKey="detailActiveTab">
          <a-tab-pane key="json" tab="JSON格式">
            <pre style="background: #f5f5f5; padding: 16px; border-radius: 4px; overflow-x: auto; max-height: 400px; overflow-y: auto;">{{ formatJsonConfig(currentTemplate) }}</pre>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-modal>
    
    <!-- LLM自动生成模板对话框 -->
    <a-modal
      v-model:open="generateModalVisible"
      title="🤖 LLM自动生成模板"
      width="600px"
      :confirm-loading="generateLoading"
      @ok="handleSubmitGenerate"
      @cancel="handleCancelGenerate"
    >
      <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="选择文档" required>
          <a-select
            v-model:value="selectedDocumentId"
            placeholder="请选择已解析的文档"
            :loading="loadingDocuments"
            show-search
            :filter-option="(input, option) => option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0"
          >
            <a-select-option
              v-for="doc in parsedDocuments"
              :key="doc.id"
              :value="doc.id"
            >
              {{ doc.file_name }} ({{ doc.status }})
            </a-select-option>
          </a-select>
          <div style="margin-top: 8px; color: #999; font-size: 12px">
            仅显示已解析的文档（parsed/chunking/chunked/completed）
          </div>
        </a-form-item>
        
        <a-form-item label="分析模式" required>
          <a-radio-group v-model:value="analysisMode">
            <a-radio value="smart_segment">
              <div>
                <div style="font-weight: 500">智能分段分析（推荐）</div>
                <div style="color: #999; font-size: 12px; margin-top: 4px">
                  • 分析文档结构<br/>
                  • 聚焦关键章节<br/>
                  • 成本可控，适合大多数文档
                </div>
              </div>
            </a-radio>
            <a-radio value="full_chunk" style="margin-top: 12px">
              <div>
                <div style="font-weight: 500">全文分块分析（最全面）</div>
                <div style="color: #999; font-size: 12px; margin-top: 4px">
                  • 分析完整文档<br/>
                  • 分块处理大文档<br/>
                  • 适合超大文档，信息最完整
                </div>
              </div>
            </a-radio>
          </a-radio-group>
        </a-form-item>
        
        <a-form-item>
          <a-alert
            message="使用本地大模型生成"
            type="info"
            show-icon
            style="margin-top: 8px"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons-vue'
import {
  getTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  validateTemplate,
  setDefaultTemplate,
  generateTemplateAsync
} from '../api/templateManagement'
import { getTask } from '../api/taskManagement'
import { getDocumentUploadList } from '../api/documentUpload'

// 数据
const templates = ref([])
const loading = ref(false)
const searchKeyword = ref('')
const filterCategory = ref(null)
const filterTemplateType = ref(null)
const modalVisible = ref(false)
const modalTitle = ref('创建模板')
const saving = ref(false)
const validating = ref(false)
const detailVisible = ref(false)
const currentTemplate = ref(null)
const activeTab = ref('json')
const detailActiveTab = ref('json')
const validationResult = ref(null)
const generateModalVisible = ref(false)
const generateLoading = ref(false)
const selectedDocumentId = ref(null)
const analysisMode = ref('smart_segment')
const parsedDocuments = ref([])
const loadingDocuments = ref(false)
const pollingTaskId = ref(null)
const pollingInterval = ref(null)

// 表单数据
const formData = reactive({
  name: '',
  description: '',
  category: 'custom',
  entity_types: {},
  edge_types: {},
  edge_type_map: {},
  is_default: false
})

const formDataJson = ref('')
const editingTemplateId = ref(null)

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

// 表格列
const columns = [
  { title: '模板名称', key: 'name', width: 200 },
  { title: '模板类型', key: 'template_type', width: 120, align: 'center' },
  { title: '分类', key: 'category', width: 120 },
  { title: '实体类型数', key: 'entity_types_count', width: 100, align: 'center' },
  { title: '关系类型数', key: 'edge_types_count', width: 100, align: 'center' },
  { title: '使用次数', key: 'usage_count', width: 100, align: 'center' },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 250 }
]

// 实体类型列表列
const entityColumns = [
  { title: '实体名称', dataIndex: 'name', key: 'name' },
  { title: '字段数量', dataIndex: 'fieldCount', key: 'fieldCount', align: 'center' }
]

// 关系类型列表列
const edgeColumns = [
  { title: '关系名称', dataIndex: 'name', key: 'name' },
  { title: '字段数量', dataIndex: 'fieldCount', key: 'fieldCount', align: 'center' }
]

// 计算属性
const entityTypesList = computed(() => {
  if (!currentTemplate.value || !currentTemplate.value.entity_types) return []
  // 如果是Memify模板，entity_types存储的是extraction配置，不显示为实体类型列表
  if (getTemplateType(currentTemplate.value) === 'Memify') {
    return []
  }
  return Object.keys(currentTemplate.value.entity_types).map(name => ({
    name,
    fieldCount: Object.keys(currentTemplate.value.entity_types[name].fields || {}).length
  }))
})

const edgeTypesList = computed(() => {
  if (!currentTemplate.value || !currentTemplate.value.edge_types) return []
  // 如果是Memify模板，edge_types存储的是enrichment配置，不显示为关系类型列表
  if (getTemplateType(currentTemplate.value) === 'Memify') {
    return []
  }
  return Object.keys(currentTemplate.value.edge_types).map(name => ({
    name,
    fieldCount: Object.keys(currentTemplate.value.edge_types[name].fields || {}).length
  }))
})

// 方法
const loadTemplates = async () => {
  loading.value = true
  try {
    const response = await getTemplates(
      pagination.current,
      pagination.pageSize,
      filterCategory.value,
      searchKeyword.value
    )
    let allTemplates = response.templates || []
    
    // 客户端筛选：按模板类型筛选
    if (filterTemplateType.value) {
      allTemplates = allTemplates.filter(template => {
        const templateType = getTemplateType(template).toLowerCase()
        return templateType === filterTemplateType.value
      })
    }
    
    templates.value = allTemplates
    pagination.total = allTemplates.length
  } catch (error) {
    console.error('加载模板列表失败:', error)
    message.error(`加载模板列表失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadTemplates()
}

const getCategoryName = (category) => {
  const names = {
    requirement: '需求文档',
    technical: '技术文档',
    product: '产品文档',
    custom: '自定义'
  }
  return names[category] || category
}

const getTemplateType = (template) => {
  // 根据analysis_mode判断模板类型
  if (template.analysis_mode) {
    if (template.analysis_mode.startsWith('cognee_memify')) {
      return 'Memify'
    } else if (template.analysis_mode.startsWith('cognee')) {
      return 'Cognify'
    }
  }
  // 根据模板名称判断（兼容旧数据）
  if (template.name) {
    if (template.name.startsWith('Memify-')) {
      return 'Memify'
    } else if (template.name.startsWith('Cognee-') || template.name.startsWith('LLM生成-')) {
      return 'Cognify'
    }
  }
  return '通用'
}

const getMemifyConfig = (template, section, key) => {
  // Memify配置存储在edge_type_map.memify_config中
  if (template.edge_type_map && template.edge_type_map.memify_config) {
    const config = template.edge_type_map.memify_config
    if (config[section] && config[section][key] !== undefined) {
      return config[section][key]
    }
  }
  // 或者直接从entity_types和edge_types中获取（兼容存储格式）
  if (section === 'extraction' && template.entity_types && template.entity_types.extraction) {
    return template.entity_types.extraction[key]
  }
  if (section === 'enrichment' && template.edge_types && template.edge_types.enrichment) {
    return template.edge_types.enrichment[key]
  }
  return null
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const formatJsonConfig = (template) => {
  if (!template) return ''
  const templateType = getTemplateType(template)
  
  if (templateType === 'Memify') {
    // Memify模板：显示memify_config配置
    const memifyConfig = template.edge_type_map?.memify_config || {
      extraction: template.entity_types?.extraction || {},
      enrichment: template.edge_types?.enrichment || {}
    }
    return JSON.stringify(memifyConfig, null, 2)
  } else {
    // Cognify模板：显示标准配置
  const config = {
    entity_types: template.entity_types || {},
    edge_types: template.edge_types || {},
    edge_type_map: template.edge_type_map || {}
  }
  return JSON.stringify(config, null, 2)
  }
}

const handleCreate = () => {
  modalTitle.value = '创建模板'
  editingTemplateId.value = null
  formData.name = ''
  formData.description = ''
  formData.category = 'custom'
  formData.entity_types = {}
  formData.edge_types = {}
  formData.edge_type_map = {}
  formData.is_default = false
  formDataJson.value = JSON.stringify({
    entity_types: {},
    edge_types: {},
    edge_type_map: {}
  }, null, 2)
  validationResult.value = null
  modalVisible.value = true
}

const handleEdit = (record) => {
  if (record.is_system) {
    message.warning('系统模板不允许编辑')
    return
  }
  modalTitle.value = '编辑模板'
  editingTemplateId.value = record.id
  formData.name = record.name
  formData.description = record.description || ''
  formData.category = record.category
  formData.entity_types = record.entity_types
  formData.edge_types = record.edge_types
  formData.edge_type_map = record.edge_type_map
  formData.is_default = record.is_default
  formDataJson.value = JSON.stringify({
    entity_types: record.entity_types,
    edge_types: record.edge_types,
    edge_type_map: record.edge_type_map
  }, null, 2)
  validationResult.value = null
  modalVisible.value = true
}

const handleView = async (record) => {
  try {
    const response = await getTemplate(record.id)
    currentTemplate.value = response
    detailVisible.value = true
  } catch (error) {
    console.error('获取模板详情失败:', error)
    message.error(`获取模板详情失败: ${error.message || '未知错误'}`)
  }
}

const handleDelete = (record) => {
  if (record.is_system) {
    message.warning('系统模板不允许删除')
    return
  }
  if (record.is_default) {
    message.warning('默认模板不允许删除，请先设置其他模板为默认模板')
    return
  }
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除模板 "${record.name}" 吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await deleteTemplate(record.id)
        message.success('模板删除成功')
        loadTemplates()
      } catch (error) {
        console.error('删除模板失败:', error)
        message.error(`删除模板失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

const handleSetDefault = async (record) => {
  try {
    await setDefaultTemplate(record.id)
    message.success('默认模板设置成功')
    loadTemplates()
  } catch (error) {
    console.error('设置默认模板失败:', error)
    message.error(`设置默认模板失败: ${error.message || '未知错误'}`)
  }
}

const handleJsonChange = () => {
  try {
    const jsonData = JSON.parse(formDataJson.value)
    formData.entity_types = jsonData.entity_types || {}
    formData.edge_types = jsonData.edge_types || {}
    formData.edge_type_map = jsonData.edge_type_map || {}
    validationResult.value = null
  } catch (error) {
    // JSON解析失败，不更新formData
  }
}

const handleValidate = async () => {
  validating.value = true
  try {
    const jsonData = JSON.parse(formDataJson.value)
    const response = await validateTemplate({
      entity_types: jsonData.entity_types || {},
      edge_types: jsonData.edge_types || {},
      edge_type_map: jsonData.edge_type_map || {}
    })
    validationResult.value = response
    if (response.valid) {
      message.success('模板校验通过')
    } else {
      message.warning('模板校验失败，请查看错误信息')
    }
  } catch (error) {
    console.error('校验模板失败:', error)
    if (error.message && error.message.includes('JSON')) {
      message.error('JSON格式错误，请检查格式')
    } else {
      message.error(`校验模板失败: ${error.message || '未知错误'}`)
    }
  } finally {
    validating.value = false
  }
}

const handleSave = async () => {
  // 先校验
  if (!validationResult.value || !validationResult.value.valid) {
    message.warning('请先校验模板，确保格式正确')
    return
  }
  
  saving.value = true
  try {
    const templateData = {
      name: formData.name,
      description: formData.description,
      category: formData.category,
      entity_types: formData.entity_types,
      edge_types: formData.edge_types,
      edge_type_map: formData.edge_type_map,
      is_default: formData.is_default
    }
    
    if (modalTitle.value === '创建模板') {
      await createTemplate(templateData)
      message.success('模板创建成功')
    } else {
      if (editingTemplateId.value) {
        await updateTemplate(editingTemplateId.value, templateData)
        message.success('模板更新成功')
      } else {
        message.error('编辑模板ID不存在')
        return
      }
    }
    
    modalVisible.value = false
    loadTemplates()
  } catch (error) {
    console.error('保存模板失败:', error)
    message.error(`保存模板失败: ${error.message || '未知错误'}`)
  } finally {
    saving.value = false
  }
}

const handleCancelModal = () => {
  modalVisible.value = false
  validationResult.value = null
  editingTemplateId.value = null
}

const handleGenerate = async () => {
  generateModalVisible.value = true
  await loadParsedDocuments()
}

const loadParsedDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    // 筛选已解析的文档
    parsedDocuments.value = (response.documents || []).filter(doc => 
      ['parsed', 'chunking', 'chunked', 'completed'].includes(doc.status)
    )
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingDocuments.value = false
  }
}

const handleSubmitGenerate = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请选择文档')
    return
  }
  
  generateLoading.value = true
  try {
    const response = await generateTemplateAsync({
      document_id: selectedDocumentId.value,
      analysis_mode: analysisMode.value,
      template_name: null,  // 自动生成
      description: null,    // 自动生成
      category: 'custom'
    })
    
    message.success('模板生成任务已提交，正在后台处理...')
    generateModalVisible.value = false
    
    // 开始轮询任务状态
    pollingTaskId.value = response.task_id
    startPollingTaskStatus(response.task_id)
    
  } catch (error) {
    console.error('提交生成任务失败:', error)
    message.error(`提交生成任务失败: ${error.message || '未知错误'}`)
  } finally {
    generateLoading.value = false
  }
}

const startPollingTaskStatus = (taskId) => {
  // 清除之前的轮询
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
  }
  
  // 开始轮询
  pollingInterval.value = setInterval(async () => {
    try {
      const task = await getTask(taskId)
      
      if (task.status === 'completed') {
        // 任务完成
        clearInterval(pollingInterval.value)
        pollingInterval.value = null
        pollingTaskId.value = null
        message.success('模板生成成功！')
        loadTemplates()  // 刷新模板列表
      } else if (task.status === 'failed') {
        // 任务失败
        clearInterval(pollingInterval.value)
        pollingInterval.value = null
        pollingTaskId.value = null
        message.error(`模板生成失败: ${task.error_message || '未知错误'}`)
      }
      // 如果任务还在运行中，继续轮询
    } catch (error) {
      console.error('查询任务状态失败:', error)
      // 继续轮询，不中断
    }
  }, 2000)  // 每2秒轮询一次
}

const handleCancelGenerate = () => {
  generateModalVisible.value = false
  selectedDocumentId.value = null
  analysisMode.value = 'smart_segment'
  
  // 清除轮询
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
  pollingTaskId.value = null
}

// 初始化
onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
</style>

