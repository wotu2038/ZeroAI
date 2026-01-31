<template>
  <a-card title="语义搜索 - 基于向量相似度的智能检索">
    <a-alert
      message="功能说明"
      description="输入自然语言查询，系统会使用 Embedding 模型生成查询向量，在 Neo4j 中执行向量相似度搜索，并使用 Cross-encoder 进行结果重排序，返回最相关的结果。"
      type="info"
      style="margin-bottom: 24px"
      show-icon
    />

    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
              <a-form-item label="选择LLM">
                <a-radio-group v-model:value="selectedProvider">
                  <a-radio value="qianwen">千问</a-radio>
                </a-radio-group>
              </a-form-item>

      <a-form-item label="搜索查询">
        <a-input-search
          v-model:value="searchQuery"
          placeholder="输入自然语言查询，例如：王五和腾讯的关系、马云的公司、阿里巴巴的创始人"
          enter-button="搜索"
          size="large"
          @search="handleSearch"
          :loading="searching"
        />
        <div style="margin-top: 8px; color: #999; font-size: 12px">
          提示：支持自然语言查询，系统会自动理解语义并检索相关知识图谱信息
        </div>
      </a-form-item>

      <a-form-item label="结果数量">
        <a-slider
          v-model:value="resultLimit"
          :min="5"
          :max="50"
          :marks="{ 5: '5', 10: '10', 20: '20', 50: '50' }"
          style="width: 100%"
        />
      </a-form-item>
    </a-form>

    <!-- 搜索流程可视化 -->
    <a-card title="搜索流程" style="margin-top: 24px" :bordered="false" v-if="searching || searchResults">
      <a-steps :current="currentStep" :items="steps" />
    </a-card>

    <!-- 搜索结果 -->
    <a-divider v-if="searchResults">搜索结果</a-divider>
    
    <div v-if="searchResults" style="margin-top: 24px">
      <a-descriptions title="搜索信息" :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="查询文本">
          <strong>{{ searchResults.query }}</strong>
        </a-descriptions-item>
        <a-descriptions-item label="结果数量">
          <a-tag color="blue">{{ searchResults.count }} 个结果</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="搜索耗时">
          {{ searchTime ? `${searchTime}ms` : 'N/A' }}
        </a-descriptions-item>
      </a-descriptions>

      <!-- 结果列表 -->
      <a-list
        v-if="searchResults.results && searchResults.results.length > 0"
        :data-source="searchResults.results"
        :pagination="{ pageSize: 10, showSizeChanger: true }"
      >
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <a-tag :color="item.type === 'node' ? 'blue' : 'green'">
                    {{ item.type === 'node' ? '节点' : '关系' }}
                  </a-tag>
                  <span style="font-weight: bold; font-size: 16px">
                    {{ getItemTitle(item) }}
                  </span>
                  <a-tag v-if="item.score" color="orange">
                    相似度: {{ (item.score * 100).toFixed(1) }}%
                  </a-tag>
                  <a-tag v-if="index < 3" color="red">Top {{ index + 1 }}</a-tag>
                </a-space>
              </template>
              <template #description>
                <div v-if="item.type === 'node'">
                  <div style="margin-bottom: 8px">
                    <strong>类型:</strong> 
                    <a-tag :color="getTypeColor(item.labels?.[0])" style="margin-left: 8px">
                      {{ item.labels?.[0] || 'Entity' }}
                    </a-tag>
                  </div>
                  <div v-if="item.properties && Object.keys(item.properties).length > 0">
                    <strong>属性:</strong>
                    <div style="margin-top: 4px; padding-left: 16px">
                      <a-descriptions size="small" :column="2" bordered>
                        <a-descriptions-item
                          v-for="(value, key) in item.properties"
                          :key="key"
                          :label="key"
                          :span="1"
                        >
                          {{ formatValue(value) }}
                        </a-descriptions-item>
                      </a-descriptions>
                    </div>
                  </div>
                </div>
                <div v-else>
                  <div style="margin-bottom: 8px">
                    <strong>关系类型:</strong> 
                    <a-tag color="blue" style="margin-left: 8px">{{ item.rel_type || item.type }}</a-tag>
                  </div>
                  <div style="margin-bottom: 8px">
                    <strong>连接:</strong> 
                    <span style="margin-left: 8px">
                      {{ item.source_name || `节点${item.source}` }} 
                      <ArrowRightOutlined /> 
                      {{ item.target_name || `节点${item.target}` }}
                    </span>
                  </div>
                  <div v-if="item.properties && Object.keys(item.properties).length > 0">
                    <strong>属性:</strong>
                    <div style="margin-top: 4px; padding-left: 16px">
                      <a-descriptions size="small" :column="2" bordered>
                        <a-descriptions-item
                          v-for="(value, key) in item.properties"
                          :key="key"
                          :label="key"
                          :span="1"
                        >
                          {{ formatValue(value) }}
                        </a-descriptions-item>
                      </a-descriptions>
                    </div>
                  </div>
                </div>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a-button type="link" size="small" @click="viewInGraph(item)">
                在图谱中查看
              </a-button>
            </template>
          </a-list-item>
        </template>
      </a-list>

      <!-- 空状态 -->
      <a-empty
        v-else
        description="未找到相关结果"
        style="margin: 40px 0"
      />
    </div>

    <!-- 搜索历史 -->
    <a-card title="搜索历史" style="margin-top: 24px" v-if="searchHistory.length > 0">
      <a-list size="small" :data-source="searchHistory" :pagination="{ pageSize: 5 }">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a @click="searchQuery = item.query; handleSearch()">
                  {{ item.query }}
                </a>
              </template>
              <template #description>
                {{ item.count }} 个结果 · {{ new Date(item.timestamp).toLocaleString() }}
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </a-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { ArrowRightOutlined } from '@ant-design/icons-vue'
import { retrieveGraph } from '../api/graph'

const router = useRouter()
const selectedProvider = ref('qianwen')
const searchQuery = ref('')
const resultLimit = ref(10)
const searching = ref(false)
const searchResults = ref(null)
const searchTime = ref(null)
const searchHistory = ref([])

const currentStep = computed(() => {
  if (!searching.value && !searchResults.value) return -1
  if (searching.value) {
    // 根据搜索进度返回步骤
    return 2 // 正在生成向量和搜索
  }
  if (searchResults.value) return 5 // 完成
  return -1
})

const steps = [
  {
    title: '输入查询',
    description: '用户输入自然语言查询'
  },
  {
    title: '生成查询向量',
    description: '使用 Embedding 模型生成查询向量'
  },
  {
    title: '向量相似度搜索',
    description: '在 Neo4j 中执行向量相似度搜索'
  },
  {
    title: '结果重排序',
    description: '使用 Cross-encoder 优化结果顺序'
  },
  {
    title: '返回结果',
    description: '显示排序后的搜索结果'
  }
]

const getItemTitle = (item) => {
  if (item.type === 'node') {
    return item.properties?.name || item.labels?.[0] || `节点 ${item.id}`
  } else {
    const sourceName = item.source_name || `节点${item.source}`
    const targetName = item.target_name || `节点${item.target}`
    const relType = item.rel_type || item.type || '关系'
    return `${sourceName} --[${relType}]--> ${targetName}`
  }
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
    Entity: 'default'
  }
  return colors[type] || 'default'
}

const formatValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    message.warning('请输入搜索查询')
    return
  }

  searching.value = true
  searchResults.value = null
  searchTime.value = null
  const startTime = Date.now()

  try {
    const result = await retrieveGraph(searchQuery.value, selectedProvider.value, resultLimit.value)
    searchTime.value = Date.now() - startTime
    
    searchResults.value = result
    
    // 添加到搜索历史
    searchHistory.value.unshift({
      query: searchQuery.value,
      count: result.count,
      timestamp: Date.now()
    })
    // 只保留最近10条
    if (searchHistory.value.length > 10) {
      searchHistory.value = searchHistory.value.slice(0, 10)
    }
    
    if (result.results && result.results.length > 0) {
      message.success(`找到 ${result.count} 个相关结果（耗时 ${searchTime.value}ms）`)
    } else {
      message.info('未找到相关结果')
    }
  } catch (error) {
    message.error('搜索失败: ' + (error.response?.data?.detail || error.message))
    console.error('Search error:', error)
  } finally {
    searching.value = false
  }
}

const viewInGraph = (item) => {
  // 跳转到图谱页面并高亮显示该节点或边
  router.push({
    name: 'graph',
    query: {
      highlight: item.type === 'node' ? item.id : `${item.source}-${item.target}`,
      type: item.type
    }
  })
}
</script>

<style scoped>
.ant-steps {
  margin-top: 16px;
}
</style>

