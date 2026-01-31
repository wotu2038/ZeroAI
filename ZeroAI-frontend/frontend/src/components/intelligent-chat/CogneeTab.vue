<template>
  <div>
    <!-- 配置区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item label="选择文档">
        <a-select
          v-model:value="selectedDocumentId"
          placeholder="请选择已解析的文档"
          style="width: 100%"
          :loading="loadingDocuments"
          :disabled="loadingDocuments || executing || splitting"
          @change="handleDocumentChange"
          allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.id"
            :value="doc.id"
          >
            {{ doc.file_name }} (ID: {{ doc.id }}){{ doc.document_id ? ` - Group ID: ${doc.document_id}` : '' }}
          </a-select-option>
        </a-select>
        <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
          没有可用的文档，请先完成文档解析
        </div>
      </a-form-item>

      <!-- 分块配置区域 -->
      <a-form-item label="分块模式">
        <a-radio-group v-model:value="chunkingMode" :disabled="executing || splitting">
          <a-radio value="smart">智能分块</a-radio>
          <a-radio value="manual">手动分块</a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- 手动分块模式：显示策略选择 -->
      <a-form-item v-if="chunkingMode === 'manual'" label="分块策略">
        <a-select
          v-model:value="chunkStrategy"
          placeholder="选择分块策略"
          style="width: 200px"
          :disabled="executing || splitting"
        >
          <a-select-option value="level_1">按一级标题（推荐）</a-select-option>
          <a-select-option value="level_2">按二级标题</a-select-option>
          <a-select-option value="level_3">按三级标题</a-select-option>
          <a-select-option value="level_4">按四级标题</a-select-option>
          <a-select-option value="level_5">按五级标题</a-select-option>
          <a-select-option value="fixed_token">按固定Token</a-select-option>
          <a-select-option value="no_split">不分块</a-select-option>
        </a-select>
      </a-form-item>

      <!-- Max Tokens输入框（两种模式都显示） -->
      <a-form-item label="Max Tokens">
        <a-input-number
          v-model:value="maxTokensPerSection"
          placeholder="每个章节的最大token数"
          :min="1000"
          :max="20000"
          :step="1000"
          style="width: 200px"
          :disabled="executing || splitting"
        >
          <template #addonBefore>Max:</template>
        </a-input-number>
        <div style="color: #999; font-size: 12px; margin-top: 4px">
          范围：1000-20000，默认：8000
        </div>
      </a-form-item>

      <a-form-item label="LLM配置">
        <a-space>
          <a-radio-group v-model:value="provider" :disabled="executing || splitting">
            <a-radio value="deepseek">DeepSeek</a-radio>
            <a-radio value="qwen">Qwen</a-radio>
            <a-radio value="kimi">Kimi</a-radio>
          </a-radio-group>
        </a-space>
      </a-form-item>

      <!-- Cognify阶段模板配置 -->
      <a-form-item label="Cognify模板">
        <a-space direction="vertical" style="width: 100%">
          <a-radio-group v-model:value="cognifyTemplateMode" :disabled="executing || splitting">
            <a-radio value="llm_generate">LLM自动生成</a-radio>
            <a-radio value="json_config">JSON手动配置</a-radio>
          </a-radio-group>
          <div v-if="cognifyTemplateMode === 'json_config'" style="width: 100%">
            <a-space style="margin-bottom: 8px">
              <a-button size="small" @click="loadCognifyExample" :disabled="executing || splitting">
                加载示例模板
              </a-button>
              <a-button size="small" @click="validateCognifyJson" :disabled="executing || splitting">
                验证JSON格式
              </a-button>
              <a-button size="small" @click="clearCognifyJson" :disabled="executing || splitting">
                清空
              </a-button>
            </a-space>
            <a-textarea
              v-model:value="cognifyTemplateConfigJson"
              placeholder='请输入JSON配置，格式：{"entity_types": {...}, "edge_types": {...}, "edge_type_map": {...}}'
              :rows="8"
              :disabled="executing || splitting"
              style="font-family: monospace; font-size: 12px"
              :class="{ 'error-border': cognifyJsonError }"
            />
            <div v-if="cognifyJsonError" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              {{ cognifyJsonError }}
            </div>
            <div v-else style="color: #999; font-size: 12px; margin-top: 4px">
              提示：JSON配置格式需包含 entity_types、edge_types、edge_type_map 字段
            </div>
          </div>
        </a-space>
      </a-form-item>

      <!-- Memify阶段模板配置 -->
      <a-form-item label="Memify模板">
        <a-space direction="vertical" style="width: 100%">
          <a-radio-group v-model:value="memifyTemplateMode" :disabled="executing || splitting">
            <a-radio value="llm_generate">LLM自动生成</a-radio>
            <a-radio value="json_config">JSON手动配置</a-radio>
          </a-radio-group>
          <div v-if="memifyTemplateMode === 'json_config'" style="width: 100%">
            <a-space style="margin-bottom: 8px">
              <a-button size="small" @click="loadMemifyExample" :disabled="executing || splitting">
                加载示例模板
              </a-button>
              <a-button size="small" @click="validateMemifyJson" :disabled="executing || splitting">
                验证JSON格式
              </a-button>
              <a-button size="small" @click="clearMemifyJson" :disabled="executing || splitting">
                清空
              </a-button>
            </a-space>
            <a-textarea
              v-model:value="memifyTemplateConfigJson"
              placeholder='请输入JSON配置，格式：{"extraction": {...}, "enrichment": {...}}'
              :rows="10"
              :disabled="executing || splitting"
              style="font-family: monospace; font-size: 12px"
              :class="{ 'error-border': memifyJsonError }"
            />
            <div v-if="memifyJsonError" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              {{ memifyJsonError }}
            </div>
            <div v-else style="color: #999; font-size: 12px; margin-top: 4px">
              提示：JSON配置格式需包含 extraction 和 enrichment 字段，支持禁用某个任务（enabled: false）
            </div>
          </div>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 分块操作区域 -->
    <a-form v-if="selectedDocumentId && (!selectedDoc?.chunks_path || needRechunk)" :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item>
        <a-space>
          <a-button 
            type="primary" 
            @click="handleSplitDocument" 
            :loading="splitting"
            :disabled="!selectedDocumentId || splitting || executing"
          >
            <template #icon><FileTextOutlined /></template>
            {{ selectedDoc?.chunks_path ? '重新分块' : '执行分块' }}
          </a-button>
          <a-button v-if="needRechunk" @click="needRechunk = false" :disabled="splitting">
            取消重新分块
          </a-button>
        </a-space>
        <div v-if="!selectedDoc?.chunks_path" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
          该文档尚未分块，请先完成文档分块
        </div>
      </a-form-item>
    </a-form>

    <!-- 分块结果展示 -->
    <a-card v-if="splitResult" title="分块结果" style="margin-bottom: 24px">
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="分块策略">
          {{ getStrategyName(splitResult.strategy) }}
        </a-descriptions-item>
        <a-descriptions-item label="章节数量">
          {{ splitResult.statistics?.total_sections || 0 }}
        </a-descriptions-item>
        <a-descriptions-item label="总Token数">
          {{ splitResult.statistics?.total_tokens || 0 }}
        </a-descriptions-item>
        <a-descriptions-item label="平均Token数">
          {{ splitResult.statistics?.avg_tokens || 0 }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- 执行区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item>
        <a-space>
          <a-button 
            type="primary" 
            @click="handleExecute" 
            :loading="executing"
            :disabled="!selectedDocumentId || executing || splitting || !selectedDoc?.chunks_path"
          >
            <template #icon><PlayCircleOutlined /></template>
            执行Cognee章节级处理
          </a-button>
          <a-button 
            v-if="selectedDoc?.chunks_path" 
            @click="needRechunk = true" 
            :disabled="executing || splitting"
          >
            重新分块
          </a-button>
          <a-button @click="handleClear" :disabled="executing || splitting">
            清空结果
          </a-button>
          <a-button 
            @click="handleViewGraph" 
            :disabled="!selectedDocumentId || executing || splitting"
            :loading="loadingGraph"
          >
            <template #icon><EyeOutlined /></template>
            查看图谱
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
          <a-descriptions-item label="节点数量">
            {{ executionResult.node_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="关系数量">
            {{ executionResult.relationship_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="Dataset名称">
            {{ executionResult.dataset_name || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag color="green">成功</a-tag>
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 图谱可视化 -->
      <a-card title="Cognee知识图谱" style="margin-bottom: 24px">
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
            <a-tag>{{ selectedNode.labels?.[0] || 'Node' }}</a-tag>
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
        </a-descriptions>
      </div>
    </a-drawer>

    <!-- 图谱查看Modal -->
    <a-modal
      v-model:open="graphModalVisible"
      title="Cognee知识图谱"
      :width="1200"
      :footer="null"
      @cancel="handleGraphModalClose"
    >
      <div v-if="viewGraphData && viewGraphData.nodes && viewGraphData.nodes.length > 0" style="height: 600px; border: 1px solid #d9d9d9; border-radius: 4px">
        <GraphVisualization 
          :data="viewGraphData"
          @nodeClick="handleNodeClick"
          @edgeClick="handleEdgeClick"
        />
      </div>
      <a-empty v-else description="暂无图谱数据" />
    </a-modal>

    <!-- 图谱未创建提示Modal -->
    <a-modal
      v-model:open="graphNotCreatedModalVisible"
      title="提示"
      :width="500"
      :footer="null"
    >
      <div style="padding: 20px 0; text-align: center;">
        <a-result
          status="warning"
          title="图谱未创建"
          sub-title="该文档尚未执行Cognee章节级处理，请先执行处理后再查看图谱。"
        >
          <template #extra>
            <a-button type="primary" @click="graphNotCreatedModalVisible = false">
              确定
            </a-button>
          </template>
        </a-result>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, LoadingOutlined, FileTextOutlined, EyeOutlined } from '@ant-design/icons-vue'
import GraphVisualization from '../GraphVisualization.vue'
import { getDocumentUploadList, splitDocument } from '../../api/documentUpload'
import { step2CogneeBuild, getCogneeGraph } from '../../api/intelligentChat'

const documents = ref([])
const loadingDocuments = ref(false)
const selectedDocumentId = ref(null)
const provider = ref('deepseek')
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)
const graphData = ref(null)
const graphCollapseActiveKey = ref([])

// 分块相关
const chunkingMode = ref('smart') // 'smart' 或 'manual'
const chunkStrategy = ref('level_1') // 手动分块时的策略
const maxTokensPerSection = ref(8000)
const splitting = ref(false)
const splitResult = ref(null)
const needRechunk = ref(false) // 是否需要重新分块

// 模板配置相关
const cognifyTemplateMode = ref('llm_generate') // 'llm_generate' 或 'json_config'
const cognifyTemplateConfigJson = ref('') // JSON配置字符串
const cognifyJsonError = ref('') // JSON验证错误信息
const memifyTemplateMode = ref('llm_generate') // 'llm_generate' 或 'json_config'
const memifyTemplateConfigJson = ref('') // JSON配置字符串
const memifyJsonError = ref('') // JSON验证错误信息

// Cognify示例模板
const cognifyExampleTemplate = {
  entity_types: {
    "Person": "人物实体，包括姓名、职位、角色等信息",
    "Technology": "技术实体，包括技术名称、版本、描述等信息",
    "Concept": "概念实体，代表理论、方法、思想等"
  },
  edge_types: {
    "CREATED_BY": "创建关系，表示技术由人物创建",
    "USES": "使用关系，表示技术使用其他技术",
    "RELATED_TO": "相关关系，表示概念之间的关联"
  },
  edge_type_map: {
    "Person": ["CREATED_BY", "RELATED_TO"],
    "Technology": ["USES", "CREATED_BY", "RELATED_TO"],
    "Concept": ["RELATED_TO"]
  }
}

// Memify示例模板
const memifyExampleTemplate = {
  extraction: {
    enabled: true,
    task: "extract_subgraph_chunks",
    node_types: ["DocumentChunk"],
    max_hops: 1,
    max_chunks: 100
  },
  enrichment: {
    enabled: true,
    task: "add_rule_associations",
    rules_nodeset_name: "default_rules",
    user_prompt_location: "coding_rule_association_agent_user.txt",
    system_prompt_location: "coding_rule_association_agent_system.txt"
  }
}

// 加载Cognify示例模板
const loadCognifyExample = () => {
  cognifyTemplateConfigJson.value = JSON.stringify(cognifyExampleTemplate, null, 2)
  cognifyJsonError.value = ''
  message.success('已加载Cognify示例模板')
}

// 加载Memify示例模板
const loadMemifyExample = () => {
  memifyTemplateConfigJson.value = JSON.stringify(memifyExampleTemplate, null, 2)
  memifyJsonError.value = ''
  message.success('已加载Memify示例模板')
}

// 验证Cognify JSON格式
const validateCognifyJson = () => {
  if (!cognifyTemplateConfigJson.value.trim()) {
    cognifyJsonError.value = 'JSON配置不能为空'
    return false
  }
  try {
    const config = JSON.parse(cognifyTemplateConfigJson.value.trim())
    // 验证必需字段
    if (!config.entity_types || typeof config.entity_types !== 'object') {
      cognifyJsonError.value = '缺少必需字段: entity_types'
      return false
    }
    if (!config.edge_types || typeof config.edge_types !== 'object') {
      cognifyJsonError.value = '缺少必需字段: edge_types'
      return false
    }
    if (!config.edge_type_map || typeof config.edge_type_map !== 'object') {
      cognifyJsonError.value = '缺少必需字段: edge_type_map'
      return false
    }
    cognifyJsonError.value = ''
    message.success('Cognify JSON格式验证通过')
    return true
  } catch (e) {
    cognifyJsonError.value = `JSON格式错误: ${e.message}`
    return false
  }
}

// 验证Memify JSON格式
const validateMemifyJson = () => {
  if (!memifyTemplateConfigJson.value.trim()) {
    memifyJsonError.value = 'JSON配置不能为空'
    return false
  }
  try {
    const config = JSON.parse(memifyTemplateConfigJson.value.trim())
    // 验证必需字段
    if (!config.extraction || typeof config.extraction !== 'object') {
      memifyJsonError.value = '缺少必需字段: extraction'
      return false
    }
    if (!config.enrichment || typeof config.enrichment !== 'object') {
      memifyJsonError.value = '缺少必需字段: enrichment'
      return false
    }
    // 验证extraction字段
    if (config.extraction.enabled !== undefined && typeof config.extraction.enabled !== 'boolean') {
      memifyJsonError.value = 'extraction.enabled 必须是布尔值'
      return false
    }
    // 验证enrichment字段
    if (config.enrichment.enabled !== undefined && typeof config.enrichment.enabled !== 'boolean') {
      memifyJsonError.value = 'enrichment.enabled 必须是布尔值'
      return false
    }
    memifyJsonError.value = ''
    message.success('Memify JSON格式验证通过')
    return true
  } catch (e) {
    memifyJsonError.value = `JSON格式错误: ${e.message}`
    return false
  }
}

// 清空Cognify JSON
const clearCognifyJson = () => {
  cognifyTemplateConfigJson.value = ''
  cognifyJsonError.value = ''
  message.info('已清空Cognify配置')
}

// 清空Memify JSON
const clearMemifyJson = () => {
  memifyTemplateConfigJson.value = ''
  memifyJsonError.value = ''
  message.info('已清空Memify配置')
}

const selectedDoc = computed(() => {
  return documents.value.find(d => d.id === selectedDocumentId.value)
})

// 节点和边详情
const selectedNode = ref(null)
const selectedEdge = ref(null)
const nodeDrawerVisible = ref(false)
const edgeDrawerVisible = ref(false)

// 图谱查看相关
const graphModalVisible = ref(false)
const graphNotCreatedModalVisible = ref(false)
const viewGraphData = ref(null)
const loadingGraph = ref(false)

const hasOtherProperties = computed(() => {
  if (!selectedNode.value || !selectedNode.value.properties) return false
  const excludeKeys = ['id', 'name', 'uuid', 'labels', 'created_at']
  return Object.keys(selectedNode.value.properties).some(key => !excludeKeys.includes(key))
})

const otherProperties = computed(() => {
  if (!selectedNode.value || !selectedNode.value.properties) return {}
  const excludeKeys = ['id', 'name', 'uuid', 'labels', 'created_at']
  const result = {}
  Object.keys(selectedNode.value.properties).forEach(key => {
    if (!excludeKeys.includes(key)) {
      result[key] = selectedNode.value.properties[key]
    }
  })
  return result
})

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    if (response && response.documents) {
      // 只显示已解析的文档（有parsed_content_path或chunks_path）
      documents.value = response.documents.filter(doc => 
        doc.parsed_content_path || doc.chunks_path
      )
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
  splitResult.value = null
  needRechunk.value = false
  // 如果文档已分块，加载分块信息
  if (selectedDoc.value?.chunks_path) {
    // 可以在这里加载分块信息，暂时不实现
  }
}

// 执行分块
const handleSplitDocument = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  if (!maxTokensPerSection.value || maxTokensPerSection.value < 1000 || maxTokensPerSection.value > 20000) {
    message.warning('每个章节的最大token数必须在1000-20000之间')
    return
  }

  splitting.value = true
  splitResult.value = null

  try {
    const strategy = chunkingMode.value === 'smart' ? 'auto' : chunkStrategy.value
    message.info(chunkingMode.value === 'smart' ? '开始执行智能分块...' : '开始执行手动分块...')
    
    const response = await splitDocument(
      selectedDocumentId.value,
      strategy,
      maxTokensPerSection.value,
      true  // saveChunks
    )
    
    splitResult.value = response
    needRechunk.value = false
    
    const strategyName = getStrategyName(response.strategy)
    message.success(`分块完成！策略: ${strategyName}, 共 ${response.statistics?.total_sections || 0} 个块`)
    
    // 刷新文档列表以获取最新的chunks_path
    await loadDocuments()
  } catch (error) {
    console.error('分块失败:', error)
    message.error(`分块失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    splitting.value = false
  }
}

// 获取策略名称
const getStrategyName = (strategy) => {
  const strategyNames = {
    'auto': '智能分块',
    'level_1': '按一级标题',
    'level_2': '按二级标题',
    'level_3': '按三级标题',
    'level_4': '按四级标题',
    'level_5': '按五级标题',
    'fixed_token': '按固定Token',
    'no_split': '不分块'
  }
  return strategyNames[strategy] || strategy
}

const handleExecute = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  const doc = selectedDoc.value
  if (!doc) {
    message.error('文档不存在')
    return
  }

  if (!doc.chunks_path) {
    message.warning('该文档尚未分块，请先完成文档分块')
    return
  }

  executing.value = true
  executionStatus.value = '正在执行Cognee章节级处理...'
  executionResult.value = null
  graphData.value = null

  try {
    // 验证并解析模板配置JSON（如果使用JSON配置模式）
    let cognifyTemplateConfigJsonObj = null
    if (cognifyTemplateMode.value === 'json_config') {
      if (!cognifyTemplateConfigJson.value.trim()) {
        message.error('Cognify模板JSON配置不能为空')
        executing.value = false
        return
      }
      if (!validateCognifyJson()) {
        executing.value = false
        return
      }
      try {
        cognifyTemplateConfigJsonObj = JSON.parse(cognifyTemplateConfigJson.value.trim())
      } catch (e) {
        message.error(`Cognify模板JSON配置格式错误: ${e.message}`)
        executing.value = false
        return
      }
    }

    let memifyTemplateConfigJsonObj = null
    if (memifyTemplateMode.value === 'json_config') {
      if (!memifyTemplateConfigJson.value.trim()) {
        message.error('Memify模板JSON配置不能为空')
        executing.value = false
        return
      }
      if (!validateMemifyJson()) {
        executing.value = false
        return
      }
      try {
        memifyTemplateConfigJsonObj = JSON.parse(memifyTemplateConfigJson.value.trim())
      } catch (e) {
        message.error(`Memify模板JSON配置格式错误: ${e.message}`)
        executing.value = false
        return
      }
    }

    // 调用API执行Cognee处理（group_id可选，如果没有则后端自动生成）
    const result = await step2CogneeBuild({
      upload_id: selectedDocumentId.value,
      group_id: doc.document_id || undefined,  // 如果有则传入，没有则让后端自动生成
      provider: provider.value,
      cognify_template_mode: cognifyTemplateMode.value,
      cognify_template_config_json: cognifyTemplateConfigJsonObj,
      memify_template_mode: memifyTemplateMode.value,
      memify_template_config_json: memifyTemplateConfigJsonObj
    })

    executionResult.value = result
    
    // 如果返回了group_id，更新文档列表中的document_id
    if (result.group_id && !doc.document_id) {
      doc.document_id = result.group_id
      // 重新加载文档列表以获取最新的document_id
      await loadDocuments()
    }
    
    message.success('Cognee章节级处理完成')

    // 获取图谱数据（使用返回的group_id或文档的document_id）
    const groupIdForGraph = result.group_id || doc.document_id
    if (groupIdForGraph) {
      try {
        const graphResult = await getCogneeGraph(groupIdForGraph)
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

// 查看图谱
const handleViewGraph = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  const doc = selectedDoc.value
  if (!doc) {
    message.error('文档不存在')
    return
  }

  // 检查是否有document_id（group_id）
  const groupId = doc.document_id
  if (!groupId) {
    message.warning('该文档尚未执行Cognee处理，无法查看图谱')
    return
  }

  loadingGraph.value = true
  viewGraphData.value = null

  try {
    const graphResult = await getCogneeGraph(groupId)
    
    // 检查图谱是否存在（通过检查节点数量）
    if (!graphResult.nodes || graphResult.nodes.length === 0) {
      // 图谱未创建，显示提示Modal
      graphNotCreatedModalVisible.value = true
    } else {
      // 图谱已创建，显示图谱Modal
      viewGraphData.value = graphResult
      graphModalVisible.value = true
    }
  } catch (error) {
    console.error('获取图谱数据失败:', error)
    message.error(`获取图谱数据失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    loadingGraph.value = false
  }
}

// 关闭图谱Modal
const handleGraphModalClose = () => {
  graphModalVisible.value = false
  viewGraphData.value = null
}

const handleNodeClick = (node) => {
  selectedNode.value = node
  nodeDrawerVisible.value = true
}

const handleEdgeClick = (edge) => {
  selectedEdge.value = edge
  edgeDrawerVisible.value = true
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
.error-border {
  border-color: #ff4d4f !important;
}

.error-border:focus {
  border-color: #ff4d4f !important;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2) !important;
}
</style>

