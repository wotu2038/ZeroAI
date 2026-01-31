<template>
  <div>
    <!-- 配置区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item label="选择文档">
        <a-select
          v-model:value="selectedDocumentId"
          placeholder="请选择要处理的文档"
          style="width: 100%"
          :loading="loadingDocuments"
          :disabled="loadingDocuments || executing"
          @change="handleDocumentChange"
          allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.id"
            :value="doc.id"
          >
            {{ doc.file_name }} (ID: {{ doc.id }})
          </a-select-option>
        </a-select>
        <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
          没有可用的文档，请先在"文档管理"中上传文档
        </div>
      </a-form-item>

      <a-form-item label="LLM配置">
        <a-radio-group v-model:value="provider" :disabled="executing">
          <a-radio value="deepseek">DeepSeek</a-radio>
          <a-radio value="qwen">Qwen</a-radio>
          <a-radio value="kimi">Kimi</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="实体关系模板">
        <a-space direction="vertical" style="width: 100%">
          <a-radio-group v-model:value="templateMode">
            <a-radio value="llm_generate">LLM自动生成</a-radio>
            <a-radio value="json_config">JSON手动配置</a-radio>
          </a-radio-group>
          <div v-if="templateMode === 'json_config'" style="width: 100%">
            <a-textarea
              v-model:value="templateConfigJson"
              placeholder='请输入JSON配置，格式：{"entity_types": {...}, "edge_types": {...}, "edge_type_map": {...}}'
              :rows="8"
              :disabled="executing"
            />
            <div style="color: #999; font-size: 12px; margin-top: 4px">
              提示：JSON配置需要包含 entity_types、edge_types 和 edge_type_map 三个字段
            </div>
          </div>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 执行区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item>
        <a-space>
          <a-button 
            type="primary" 
            @click="handleExecute" 
            :loading="executing"
            :disabled="!selectedDocumentId || executing"
          >
            <template #icon><PlayCircleOutlined /></template>
            执行Graphiti文档级处理
          </a-button>
          <a-button @click="handleClear" :disabled="executing">
            清空结果
          </a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 结果区域 -->
    <div v-if="executing" style="text-align: center; padding: 40px">
      <a-spin size="large">
        <template #indicator>
          <LoadingOutlined style="font-size: 24px" spin />
        </template>
      </a-spin>
      <div style="margin-top: 12px; color: #999">
        {{ executionStatus }}
      </div>
    </div>

    <div v-else-if="executionResult">
      <!-- 执行结果摘要 -->
      <a-card title="执行结果" style="margin-bottom: 24px">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="Episode UUID">
            {{ executionResult.episode_uuid || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="Entity数量">
            {{ executionResult.entity_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="Edge数量">
            {{ executionResult.edge_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag color="green">成功</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模板模式" v-if="executionResult.template_mode">
            <a-tag :color="executionResult.template_mode === 'llm_generate' ? 'blue' : 'green'">
              {{ executionResult.template_mode === 'llm_generate' ? 'LLM自动生成' : 'JSON手动配置' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模板ID" v-if="executionResult.template_id">
            {{ executionResult.template_id }}
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- Cognee TextSummary 引用关系 -->
      <a-card 
        v-if="executionResult.text_summary_reference" 
        title="Cognee TextSummary 引用关系" 
        style="margin-bottom: 24px"
      >
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="引用状态">
            <a-tag :color="executionResult.text_summary_reference.established ? 'green' : 'orange'">
              {{ executionResult.text_summary_reference.established ? '已建立' : '未建立' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item 
            label="TextSummary UUID" 
            v-if="executionResult.text_summary_reference.text_summary_uuid"
          >
            {{ executionResult.text_summary_reference.text_summary_uuid }}
          </a-descriptions-item>
          <a-descriptions-item 
            label="TextSummary 内容预览" 
            v-if="executionResult.text_summary_reference.text_summary_text"
          >
            <div style="max-height: 100px; overflow-y: auto; padding: 8px; background: #f5f5f5; border-radius: 4px;">
              {{ executionResult.text_summary_reference.text_summary_text }}
            </div>
          </a-descriptions-item>
          <a-descriptions-item 
            label="说明" 
            v-if="executionResult.text_summary_reference.error"
          >
            <a-alert 
              :message="executionResult.text_summary_reference.error" 
              type="info" 
              show-icon 
              :closable="false"
            />
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 图谱可视化 -->
      <a-card title="Graphiti知识图谱" style="margin-bottom: 24px">
        <a-collapse v-model:activeKey="graphCollapseActiveKey">
          <a-collapse-panel key="graph" header="查看图谱">
            <div style="height: 600px; border: 1px solid #d9d9d9; border-radius: 4px">
              <GraphVisualization 
                v-if="graphData && graphData.nodes && graphData.nodes.length > 0"
                :data="graphData"
                @nodeClick="handleNodeClick"
                @edgeClick="handleEdgeClick"
              />
              <a-empty v-else description="暂无图谱数据" />
            </div>
          </a-collapse-panel>
        </a-collapse>
      </a-card>

      <!-- Entity列表 -->
      <a-card v-if="executionResult.entities && executionResult.entities.length > 0" title="Entity列表" style="margin-bottom: 24px">
        <a-table
          :columns="entityColumns"
          :data-source="executionResult.entities"
          :pagination="{ pageSize: 10 }"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'labels'">
              <a-space>
                <a-tag v-for="label in record.labels" :key="label" :color="getTypeColor(label)">
                  {{ label }}
                </a-tag>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- Edge列表 -->
      <a-card v-if="executionResult.edges && executionResult.edges.length > 0" title="Edge列表">
        <a-table
          :columns="edgeColumns"
          :data-source="executionResult.edges"
          :pagination="{ pageSize: 10 }"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'type'">
              <a-tag color="blue">{{ record.type }}</a-tag>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 空状态 -->
    <a-empty
      v-else
      description="请选择文档并点击执行按钮开始处理"
      style="margin: 60px 0"
    />

    <!-- 节点详情抽屉 -->
    <a-drawer
      v-model:open="nodeDrawerVisible"
      title="节点属性"
      placement="right"
      :width="400"
      @close="selectedNode = null"
    >
      <div v-if="selectedNode" style="padding: 16px 0;">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="ID">{{ selectedNode.id }}</a-descriptions-item>
          <a-descriptions-item label="名称">{{ selectedNode.properties?.name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="类型">
            <a-tag>{{ selectedNode.labels?.[0] || 'Entity' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="所有标签">
            <a-space>
              <a-tag v-for="label in selectedNode.labels" :key="label">{{ label }}</a-tag>
            </a-space>
          </a-descriptions-item>
          <a-descriptions-item label="其他属性" v-if="hasOtherProperties">
            <div style="max-height: 300px; overflow-y: auto;">
              <a-descriptions :column="1" size="small" bordered>
                <a-descriptions-item 
                  v-for="(value, key) in otherProperties" 
                  :key="key"
                  :label="key"
                >
                  <pre style="margin: 0; white-space: pre-wrap; word-break: break-all;">{{ formatPropertyValue(value) }}</pre>
                </a-descriptions-item>
              </a-descriptions>
            </div>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-drawer>

    <!-- 边详情抽屉 -->
    <a-drawer
      v-model:open="edgeDrawerVisible"
      title="关系属性"
      placement="right"
      :width="400"
      @close="selectedEdge = null"
    >
      <div v-if="selectedEdge" style="padding: 16px 0;">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="ID">{{ selectedEdge.id }}</a-descriptions-item>
          <a-descriptions-item label="类型">
            <a-tag color="green">{{ selectedEdge.type || 'RELATES_TO' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="源节点">{{ selectedEdge.source }}</a-descriptions-item>
          <a-descriptions-item label="目标节点">{{ selectedEdge.target }}</a-descriptions-item>
          <a-descriptions-item label="其他属性" v-if="hasOtherEdgeProperties">
            <div style="max-height: 300px; overflow-y: auto;">
              <a-descriptions :column="1" size="small" bordered>
                <a-descriptions-item 
                  v-for="(value, key) in otherEdgeProperties" 
                  :key="key"
                  :label="key"
                >
                  <pre style="margin: 0; white-space: pre-wrap; word-break: break-all;">{{ formatPropertyValue(value) }}</pre>
                </a-descriptions-item>
              </a-descriptions>
            </div>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import GraphVisualization from '../GraphVisualization.vue'
import { getDocumentUploadList } from '../../api/documentUpload'
import { step1GraphitiEpisode, getGraphitiGraph } from '../../api/intelligentChat'

const documents = ref([])
const loadingDocuments = ref(false)
const selectedDocumentId = ref(null)
const provider = ref('deepseek')
const templateMode = ref('llm_generate')  // 默认使用 LLM 生成
const templateConfigJson = ref('')
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)
const graphData = ref(null)
const graphCollapseActiveKey = ref([])

// 节点和边详情
const selectedNode = ref(null)
const selectedEdge = ref(null)
const nodeDrawerVisible = ref(false)
const edgeDrawerVisible = ref(false)

// 表格列定义
const entityColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
  { title: '名称', dataIndex: ['properties', 'name'], key: 'name' },
  { title: '类型', key: 'labels', width: 150 },
  { title: 'UUID', dataIndex: ['properties', 'uuid'], key: 'uuid' }
]

const edgeColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 100 },
  { title: '类型', key: 'type', width: 150 },
  { title: '源节点', dataIndex: 'source', key: 'source' },
  { title: '目标节点', dataIndex: 'target', key: 'target' }
]

const hasOtherProperties = computed(() => {
  if (!selectedNode.value || !selectedNode.value.properties) return false
  const excludeKeys = ['id', 'name', 'uuid', 'labels', 'created_at', 'name_embedding', 'summary']
  return Object.keys(selectedNode.value.properties).some(key => !excludeKeys.includes(key))
})

const otherProperties = computed(() => {
  if (!selectedNode.value || !selectedNode.value.properties) return {}
  const excludeKeys = ['id', 'name', 'uuid', 'labels', 'created_at', 'name_embedding', 'summary']
  const result = {}
  Object.keys(selectedNode.value.properties).forEach(key => {
    if (!excludeKeys.includes(key)) {
      result[key] = selectedNode.value.properties[key]
    }
  })
  return result
})

const hasOtherEdgeProperties = computed(() => {
  if (!selectedEdge.value || !selectedEdge.value.properties) return false
  const excludeKeys = ['id', 'type', 'source', 'target', 'uuid', 'source_node_uuid', 'target_node_uuid']
  return Object.keys(selectedEdge.value.properties).some(key => !excludeKeys.includes(key))
})

const otherEdgeProperties = computed(() => {
  if (!selectedEdge.value || !selectedEdge.value.properties) return {}
  const excludeKeys = ['id', 'type', 'source', 'target', 'uuid', 'source_node_uuid', 'target_node_uuid']
  const result = {}
  Object.keys(selectedEdge.value.properties).forEach(key => {
    if (!excludeKeys.includes(key)) {
      result[key] = selectedEdge.value.properties[key]
    }
  })
  return result
})

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    if (response && response.documents) {
      // Graphiti 只需要已解析的文档（有 parsed_content_path 即可）
      documents.value = response.documents.filter(doc => doc.parsed_content_path)
    } else {
      documents.value = []
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
    documents.value = []
  } finally {
    loadingDocuments.value = false
  }
}

const handleDocumentChange = () => {
  executionResult.value = null
  graphData.value = null
}

const handleExecute = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  const selectedDoc = documents.value.find(d => d.id === selectedDocumentId.value)
  if (!selectedDoc) {
    message.error('文档不存在')
    return
  }

  executing.value = true
  executionStatus.value = '正在执行Graphiti文档级处理...'
  executionResult.value = null
  graphData.value = null

  try {
    // 解析 JSON 配置（如果是 json_config 模式）
    let templateConfigJsonObj = null
    if (templateMode.value === 'json_config') {
      if (!templateConfigJson.value || !templateConfigJson.value.trim()) {
        message.error('JSON配置模式必须提供模板配置JSON')
        return
      }
      try {
        templateConfigJsonObj = JSON.parse(templateConfigJson.value)
      } catch (e) {
        message.error(`JSON配置格式错误: ${e.message}`)
        return
      }
    }

    // 调用API执行Graphiti处理
    const result = await step1GraphitiEpisode({
      upload_id: selectedDocumentId.value,
      provider: provider.value,
      template_mode: templateMode.value,
      template_config_json: templateConfigJsonObj
    })

    executionResult.value = result
    message.success('Graphiti文档级处理完成')

    // 获取图谱数据
    if (result.group_id) {
      try {
        const graphResult = await getGraphitiGraph(result.group_id)
        graphData.value = graphResult
        graphCollapseActiveKey.value = ['graph']
      } catch (error) {
        console.error('获取图谱数据失败:', error)
        message.warning('获取图谱数据失败，但处理已完成')
      }
    }
  } catch (error) {
    console.error('执行失败:', error)
    message.error(`执行失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    executing.value = false
    executionStatus.value = ''
  }
}

const handleClear = () => {
  executionResult.value = null
  graphData.value = null
  graphCollapseActiveKey.value = []
  message.success('结果已清空')
}

const handleNodeClick = (node) => {
  selectedNode.value = node
  nodeDrawerVisible.value = true
}

const handleEdgeClick = (edge) => {
  selectedEdge.value = edge
  edgeDrawerVisible.value = true
}

const getTypeColor = (type) => {
  const colors = {
    Person: 'blue',
    Organization: 'green',
    Location: 'orange',
    Concept: 'purple',
    Event: 'pink',
    Product: 'cyan',
    Technology: 'geekblue',
    Entity: 'default',
    Episodic: 'purple',
    Requirement: 'green',
    Feature: 'blue',
    Module: 'cyan',
    Community: 'purple'
  }
  return colors[type] || 'default'
}

const formatPropertyValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
</style>

