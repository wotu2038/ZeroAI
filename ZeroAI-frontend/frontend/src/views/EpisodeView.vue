<template>
  <a-card title="添加 Episode - 自动提取实体和关系">
    <a-alert
      message="功能说明"
      description="输入文本内容，Graphiti 会自动使用 LLM 提取实体和关系，生成 Embedding 向量，并存储到 Neo4j 知识图谱中。"
      type="info"
      style="margin-bottom: 24px"
      show-icon
    />

    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
      <a-form-item label="选择LLM">
        <a-radio-group v-model:value="selectedProvider">
          <a-radio value="qianwen">千问</a-radio>
          <a-radio value="local">本地大模型</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="输入文本">
        <a-textarea
          v-model:value="inputText"
          :rows="8"
          placeholder="请输入要提取实体和关系的文本内容，例如：&#10;王五是一名高级产品经理，目前在腾讯公司工作，负责微信产品的设计和开发。"
          :disabled="processing"
        />
        <div style="margin-top: 8px; color: #999; font-size: 12px">
          提示：输入自然语言文本，系统会自动识别其中的实体（人物、组织、地点等）和关系（工作关系、合作关系等）
        </div>
      </a-form-item>

      <a-form-item label="元数据（可选）">
        <a-space direction="vertical" style="width: 100%">
          <a-input
            v-model:value="metadata.name"
            placeholder="Episode 名称（可选）"
            :disabled="processing"
          />
          <a-input
            v-model:value="metadata.source_description"
            placeholder="数据来源描述（可选）"
            :disabled="processing"
          />
        </a-space>
      </a-form-item>

      <a-form-item :wrapper-col="{ offset: 4, span: 20 }">
        <a-space>
          <a-button type="primary" @click="handleAddEpisode" :loading="processing" size="large">
            <template #icon><PlusOutlined /></template>
            添加 Episode
          </a-button>
          <a-button @click="handleClear" :disabled="processing">清空</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 处理结果 -->
    <a-divider v-if="result">处理结果</a-divider>
    
    <div v-if="result" style="margin-top: 24px">
      <a-descriptions title="Episode 信息" :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="Episode ID">
          {{ result.episode_id || 'N/A' }}
        </a-descriptions-item>
        <a-descriptions-item label="输入文本">
          <div style="max-height: 200px; overflow-y: auto; white-space: pre-wrap">
            {{ result.content }}
          </div>
        </a-descriptions-item>
        <a-descriptions-item label="创建的实体数">
          <a-tag color="blue">{{ result.entities_created || 0 }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建的关系数">
          <a-tag color="green">{{ result.relationships_created || 0 }}</a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 提取的实体 -->
      <a-card title="提取的实体" style="margin-bottom: 16px" v-if="result.entities && result.entities.length > 0">
        <a-table
          :columns="entityColumns"
          :data-source="result.entities"
          :pagination="{ pageSize: 10 }"
          size="small"
          bordered
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'type'">
              <a-tag :color="getTypeColor(record.type)">
                {{ record.type }}
              </a-tag>
            </template>
            <template v-if="column.key === 'properties'">
              <a-descriptions size="small" :column="1" bordered>
                <a-descriptions-item
                  v-for="(value, key) in record.properties"
                  :key="key"
                  :label="key"
                >
                  {{ value }}
                </a-descriptions-item>
              </a-descriptions>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 提取的关系 -->
      <a-card title="提取的关系" v-if="result.relationships && result.relationships.length > 0">
        <a-table
          :columns="relationshipColumns"
          :data-source="result.relationships"
          :pagination="{ pageSize: 10 }"
          size="small"
          bordered
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'type'">
              <a-tag color="blue">{{ record.type }}</a-tag>
            </template>
            <template v-if="column.key === 'properties'">
              <a-descriptions size="small" :column="1" bordered>
                <a-descriptions-item
                  v-for="(value, key) in record.properties"
                  :key="key"
                  :label="key"
                >
                  {{ value }}
                </a-descriptions-item>
              </a-descriptions>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 空状态 -->
      <a-empty
        v-if="(!result.entities || result.entities.length === 0) && (!result.relationships || result.relationships.length === 0)"
        description="未提取到实体或关系"
        style="margin: 40px 0"
      />
    </div>

    <!-- 处理流程说明 -->
    <a-card title="处理流程" style="margin-top: 24px" :bordered="false">
      <a-steps :current="currentStep" :items="steps" />
    </a-card>
  </a-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { extractEntities, getProviders } from '../api/llm'

const selectedProvider = ref('qianwen')
const inputText = ref('')
const processing = ref(false)
const result = ref(null)
const availableProviders = ref([])

const metadata = ref({
  name: '',
  source_description: ''
})

const entityColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'type', key: 'type' },
  { title: '属性', dataIndex: 'properties', key: 'properties', width: 300 }
]

const relationshipColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '源节点', dataIndex: 'source', key: 'source' },
  { title: '关系类型', dataIndex: 'type', key: 'type' },
  { title: '目标节点', dataIndex: 'target', key: 'target' },
  { title: '属性', dataIndex: 'properties', key: 'properties', width: 300 }
]

const currentStep = computed(() => {
  if (!processing.value && !result.value) {
    if (inputText.value.trim()) return 0 // 已输入文本
    return -1 // 未开始
  }
  if (processing.value) return 2 // 处理中（LLM分析 + Embedding生成）
  if (result.value) return 4 // 完成
  return -1
})

const steps = [
  {
    title: '输入文本',
    description: '用户输入要处理的文本内容'
  },
  {
    title: 'LLM 分析',
    description: '使用 LLM 提取实体和关系'
  },
  {
    title: '生成 Embedding',
    description: '为实体和关系生成向量表示'
  },
  {
    title: '存储到 Neo4j',
    description: '将数据存储到图数据库'
  },
  {
    title: '完成',
    description: '处理完成，显示结果'
  }
]

const getTypeColor = (type) => {
  const colors = {
    Person: 'blue',
    Organization: 'green',
    Location: 'orange',
    Concept: 'purple',
    Event: 'pink',
    Product: 'cyan',
    Technology: 'geekblue'
  }
  return colors[type] || 'default'
}

const handleAddEpisode = async () => {
  if (!inputText.value.trim()) {
    message.warning('请输入文本内容')
    return
  }

  processing.value = true
  result.value = null

  try {
    const requestData = {
      provider: selectedProvider.value,
      text: inputText.value.trim(),
      metadata: {}
    }

    // 添加可选的元数据
    if (metadata.value.name) {
      requestData.metadata.name = metadata.value.name
    }
    if (metadata.value.source_description) {
      requestData.metadata.source_description = metadata.value.source_description
    }
    if (Object.keys(requestData.metadata).length === 0) {
      delete requestData.metadata
    }

    const response = await extractEntities(requestData)
    result.value = {
      episode_id: response.episode_id,
      content: inputText.value.trim(),
      entities_created: response.entities_created || 0,
      relationships_created: response.relationships_created || 0,
      entities: response.extracted?.entities || [],
      relationships: response.extracted?.relationships || []
    }

    message.success(
      `成功提取 ${result.value.entities_created} 个实体和 ${result.value.relationships_created} 个关系`
    )
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message || '未知错误'
    message.error({
      content: `添加 Episode 失败: ${errorMsg}`,
      duration: 8, // 显示更长时间以便用户阅读
      style: { whiteSpace: 'pre-wrap' } // 支持换行显示
    })
    console.error('Add episode error:', error)
    
    // 如果是 response_format 错误，提示用户
    if (errorMsg.includes('response_format') || errorMsg.includes('unavailable')) {
      message.warning({
        content: '提示：当前 LLM 提供商不支持 Graphiti 的 response_format 参数。',
        duration: 10
      })
    }
  } finally {
    processing.value = false
  }
}

const handleClear = () => {
  inputText.value = ''
  metadata.value = {
    name: '',
    source_description: ''
  }
  result.value = null
}

const loadProviders = async () => {
  try {
    availableProviders.value = await getProviders()
    if (availableProviders.value.length > 0 && !availableProviders.value.includes(selectedProvider.value)) {
      selectedProvider.value = availableProviders.value[0]
    }
  } catch (error) {
    console.error('获取提供商失败:', error)
  }
}

loadProviders()
</script>

<style scoped>
.ant-steps {
  margin-top: 16px;
}
</style>

