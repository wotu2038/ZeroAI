<template>
  <a-card title="查关系 - 关系路径查询">
    <a-alert
      message="功能说明"
      description="查找实体之间的关系路径。支持两种模式：1) 输入两个实体名称，查找它们之间的所有路径；2) 只输入一个实体名称，查找该实体的所有关系链。"
      type="info"
      style="margin-bottom: 24px"
      show-icon
    />

    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
      <a-form-item label="查询模式">
        <a-radio-group v-model:value="queryMode" @change="handleModeChange">
          <a-radio value="between">两个实体之间</a-radio>
          <a-radio value="single">单个实体的关系链</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="源实体">
        <a-input
          v-model:value="sourceEntity"
          placeholder="输入源实体名称，例如：马云"
          size="large"
          :disabled="searching"
        />
      </a-form-item>

      <a-form-item v-if="queryMode === 'between'" label="目标实体">
        <a-input
          v-model:value="targetEntity"
          placeholder="输入目标实体名称，例如：淘宝"
          size="large"
          :disabled="searching"
        />
      </a-form-item>

      <a-form-item label="最大路径长度">
        <a-slider
          v-model:value="maxDepth"
          :min="1"
          :max="10"
          :marks="{ 1: '1', 3: '3', 5: '5', 10: '10' }"
          style="width: 100%"
        />
        <div style="margin-top: 8px; color: #999; font-size: 12px">
          提示：路径长度表示从源实体到目标实体需要经过的关系数量（跳数）
        </div>
      </a-form-item>

      <a-form-item label="结果数量限制">
        <a-input-number
          v-model:value="resultLimit"
          :min="10"
          :max="500"
          :step="10"
          style="width: 100%"
        />
      </a-form-item>

      <a-form-item :wrapper-col="{ offset: 4, span: 20 }">
        <a-space>
          <a-button type="primary" @click="handleSearch" :loading="searching" size="large">
            <template #icon><SearchOutlined /></template>
            查询路径
          </a-button>
          <a-button @click="handleClear" :disabled="searching">清空</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <!-- 查询结果 -->
    <a-divider v-if="pathResults">查询结果</a-divider>
    
    <div v-if="pathResults" style="margin-top: 24px">
      <a-descriptions title="查询信息" :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="源实体">
          <strong>{{ pathResults.source }}</strong>
        </a-descriptions-item>
        <a-descriptions-item v-if="pathResults.target" label="目标实体">
          <strong>{{ pathResults.target }}</strong>
        </a-descriptions-item>
        <a-descriptions-item label="找到的路径数">
          <a-tag color="blue">{{ pathResults.total_paths }} 条路径</a-tag>
        </a-descriptions-item>
        <a-descriptions-item v-if="pathResults.shortest_length !== null" label="最短路径长度">
          <a-tag color="red">{{ pathResults.shortest_length }} 跳</a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 路径列表 -->
      <a-typography-title :level="5">路径详情</a-typography-title>
      <a-list
        v-if="pathResults.paths && pathResults.paths.length > 0"
        :data-source="pathResults.paths"
        :pagination="{ pageSize: 5, showSizeChanger: true }"
      >
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <a-tag :color="item.is_shortest ? 'red' : 'blue'">
                    {{ item.is_shortest ? '最短路径' : `路径 ${index + 1}` }}
                  </a-tag>
                  <span style="font-weight: bold; font-size: 16px">
                    路径长度: {{ item.length }} 跳
                  </span>
                </a-space>
              </template>
              <template #description>
                <div style="margin-top: 12px">
                  <div
                    v-for="(segment, segIndex) in item.segments"
                    :key="segIndex"
                    style="margin-bottom: 8px; padding: 8px; background: #f5f5f5; border-radius: 4px"
                  >
                    <a-space>
                      <span style="font-weight: bold">{{ segment.source_name }}</span>
                      <ArrowRightOutlined />
                      <a-tag :color="item.is_shortest ? 'red' : 'blue'">
                        {{ segment.relation_type }}
                      </a-tag>
                      <ArrowRightOutlined />
                      <span style="font-weight: bold">{{ segment.target_name }}</span>
                      <a-tag v-if="segment.relation_fact" color="green" style="margin-left: 8px">
                        {{ segment.relation_fact }}
                      </a-tag>
                    </a-space>
                  </div>
                </div>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a-button type="link" size="small" @click="viewPathInGraph(item)">
                在图谱中查看
              </a-button>
            </template>
          </a-list-item>
        </template>
      </a-list>

      <!-- 空状态 -->
      <a-empty
        v-else
        description="未找到相关路径"
        style="margin: 40px 0"
      />
    </div>
  </a-card>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { SearchOutlined, ArrowRightOutlined } from '@ant-design/icons-vue'
import { findPaths } from '../api/graph'

const router = useRouter()
const queryMode = ref('between')
const sourceEntity = ref('')
const targetEntity = ref('')
const maxDepth = ref(10)
const resultLimit = ref(100)
const searching = ref(false)
const pathResults = ref(null)

const handleModeChange = () => {
  // 切换模式时清空结果
  pathResults.value = null
  if (queryMode.value === 'single') {
    targetEntity.value = ''
  }
}

const handleSearch = async () => {
  if (!sourceEntity.value.trim()) {
    message.warning('请输入源实体名称')
    return
  }

  if (queryMode.value === 'between' && !targetEntity.value.trim()) {
    message.warning('请输入目标实体名称')
    return
  }

  searching.value = true
  pathResults.value = null

  try {
    const result = await findPaths(
      sourceEntity.value.trim(),
      queryMode.value === 'between' ? targetEntity.value.trim() : null,
      maxDepth.value,
      resultLimit.value
    )
    
    pathResults.value = result
    
    if (result.paths && result.paths.length > 0) {
      const shortestCount = result.paths.filter(p => p.is_shortest).length
      message.success(
        `找到 ${result.total_paths} 条路径${shortestCount > 0 ? `，其中 ${shortestCount} 条为最短路径` : ''}`
      )
    } else {
      message.info('未找到相关路径')
    }
  } catch (error) {
    message.error('查询失败: ' + (error.response?.data?.detail || error.message))
    console.error('Path search error:', error)
  } finally {
    searching.value = false
  }
}

const handleClear = () => {
  sourceEntity.value = ''
  targetEntity.value = ''
  pathResults.value = null
}

const viewPathInGraph = (path) => {
  // 跳转到图谱页面并高亮显示该路径
  const nodeIds = []
  const edgeIds = []
  
  // 提取路径中的所有节点和边ID
  path.segments.forEach((segment, index) => {
    if (index === 0) {
      nodeIds.push(segment.source_id)
    }
    nodeIds.push(segment.target_id)
    edgeIds.push(segment.relation_id)
  })
  
  router.push({
    name: 'graph',
    query: {
      highlightPath: JSON.stringify({
        nodes: nodeIds,
        edges: edgeIds,
        isShortest: path.is_shortest
      })
    }
  })
}
</script>

<style scoped>
.ant-list-item {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  margin-bottom: 12px;
  padding: 16px;
}
</style>

