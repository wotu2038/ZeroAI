<template>
  <div style="width: 100%; height: 100vh; display: flex; flex-direction: column;">
    <div style="padding: 16px; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center;">
      <a-space>
        <span>知识图谱可视化</span>
        <a-tag color="blue">节点: {{ stats.node_count || 0 }}</a-tag>
        <a-tag color="green">关系: {{ stats.relationship_count || 0 }}</a-tag>
      </a-space>
      <a-input-search
        v-model:value="searchQuery"
        placeholder="查关系（输入实体名称，如：马云 马化腾）"
        style="width: 300px"
        @search="handleSearch"
        :loading="searching"
      >
        <template #enterButton>
          <a-button type="primary">查关系</a-button>
        </template>
      </a-input-search>
    </div>
    <div style="flex: 1; width: 100%; height: 100%; overflow: hidden;">
      <GraphVisualization 
        ref="graphRef"
        @nodeClick="handleNodeClick"
        @edgeClick="handleEdgeClick"
      />
    </div>
    
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
          <a-descriptions-item label="创建时间" v-if="selectedNode.properties?.created_at">
            {{ new Date(selectedNode.properties.created_at).toLocaleString() }}
          </a-descriptions-item>
          <a-descriptions-item label="其他属性" v-if="hasOtherProperties">
            <div style="max-height: 300px; overflow-y: auto;">
              <a-descriptions :column="1" size="small" bordered>
                <a-descriptions-item 
                  v-for="(value, key) in otherProperties" 
                  :key="key"
                  :label="key"
                >
                  <div v-if="isEmbeddingArray(value)" style="position: relative; display: inline-block;">
                    <span>
                      [{{ Array.isArray(value) && value.length > 0 ? value[0].toFixed(6) : '-' }}<span 
                        style="color: #1890ff; cursor: pointer; text-decoration: underline;" 
                        @mouseenter="showFullEmbedding = `node_${key}`" 
                        @mouseleave="showFullEmbedding = null"
                      >, ...] ({{ value.length }} 个值)</span>
                    </span>
                    <div 
                      v-if="showFullEmbedding === `node_${key}`" 
                      style="position: fixed; background: white; border: 1px solid #d9d9d9; padding: 12px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 9999; max-width: 600px; max-height: 400px; overflow: auto; pointer-events: none;"
                      :style="{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }"
                    >
                      <div style="font-weight: bold; margin-bottom: 8px; color: #1890ff;">完整 Embedding 向量 ({{ value.length }} 维)</div>
                      <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 11px; line-height: 1.4;">{{ formatPropertyValue(value) }}</pre>
                    </div>
                  </div>
                  <pre v-else style="margin: 0; white-space: pre-wrap; word-break: break-all;">{{ formatPropertyValue(value) }}</pre>
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
          <a-descriptions-item label="关系名称" v-if="selectedEdge.properties?.name">
            {{ selectedEdge.properties.name }}
          </a-descriptions-item>
          <a-descriptions-item label="关系事实" v-if="selectedEdge.properties?.fact">
            {{ selectedEdge.properties.fact }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" v-if="selectedEdge.properties?.created_at">
            {{ new Date(selectedEdge.properties.created_at).toLocaleString() }}
          </a-descriptions-item>
          <a-descriptions-item label="其他属性" v-if="hasOtherEdgeProperties">
            <div style="max-height: 300px; overflow-y: auto;">
              <a-descriptions :column="1" size="small" bordered>
                <a-descriptions-item 
                  v-for="(value, key) in otherEdgeProperties" 
                  :key="key"
                  :label="key"
                >
                  <div v-if="isEmbeddingArray(value)" style="position: relative; display: inline-block;">
                    <span>
                      [{{ Array.isArray(value) && value.length > 0 ? value[0].toFixed(6) : '-' }}<span 
                        style="color: #1890ff; cursor: pointer; text-decoration: underline;" 
                        @mouseenter="showFullEmbedding = `edge_${key}`" 
                        @mouseleave="showFullEmbedding = null"
                      >, ...] ({{ value.length }} 个值)</span>
                    </span>
                    <div 
                      v-if="showFullEmbedding === `edge_${key}`" 
                      style="position: fixed; background: white; border: 1px solid #d9d9d9; padding: 12px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 9999; max-width: 600px; max-height: 400px; overflow: auto; pointer-events: none;"
                      :style="{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }"
                    >
                      <div style="font-weight: bold; margin-bottom: 8px; color: #1890ff;">完整 Embedding 向量 ({{ value.length }} 维)</div>
                      <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 11px; line-height: 1.4;">{{ formatPropertyValue(value) }}</pre>
                    </div>
                  </div>
                  <pre v-else style="margin: 0; white-space: pre-wrap; word-break: break-all;">{{ formatPropertyValue(value) }}</pre>
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
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import GraphVisualization from '../components/GraphVisualization.vue'
import { getGraphStats, getGraphData, findPaths } from '../api/graph'

const graphRef = ref(null)
const graphData = ref({ nodes: [], edges: [] })
const searchQuery = ref('')
const searching = ref(false)

const stats = ref({
  node_count: 0,
  relationship_count: 0
})

// 节点和边详情抽屉
const selectedNode = ref(null)
const selectedEdge = ref(null)
const nodeDrawerVisible = ref(false)
const edgeDrawerVisible = ref(false)
const showFullEmbedding = ref(null) // 当前显示完整内容的 Embedding 字段名

const handleNodeClick = (node) => {
  selectedNode.value = node
  nodeDrawerVisible.value = true
}

const handleEdgeClick = (edge) => {
  selectedEdge.value = edge
  edgeDrawerVisible.value = true
}

const hasOtherProperties = computed(() => {
  if (!selectedNode.value?.properties) return false
  const excludeKeys = ['name', 'created_at', 'name_embedding', 'name_emb']
  return Object.keys(selectedNode.value.properties).some(key => !excludeKeys.includes(key))
})

const otherProperties = computed(() => {
  if (!selectedNode.value?.properties) return {}
  const excludeKeys = ['name', 'created_at', 'name_embedding', 'name_emb']
  const result = {}
  for (const [key, value] of Object.entries(selectedNode.value.properties)) {
    if (!excludeKeys.includes(key)) {
      result[key] = value
    }
  }
  return result
})

const hasOtherEdgeProperties = computed(() => {
  if (!selectedEdge.value?.properties) return false
  const excludeKeys = ['name', 'fact', 'created_at', 'fact_embedding']
  return Object.keys(selectedEdge.value.properties).some(key => !excludeKeys.includes(key))
})

const otherEdgeProperties = computed(() => {
  if (!selectedEdge.value?.properties) return {}
  const excludeKeys = ['name', 'fact', 'created_at', 'fact_embedding']
  const result = {}
  for (const [key, value] of Object.entries(selectedEdge.value.properties)) {
    if (!excludeKeys.includes(key)) {
      result[key] = value
    }
  }
  return result
})

const formatPropertyValue = (value) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const isEmbeddingArray = (value) => {
  // 判断是否是 Embedding 向量数组（通常是浮点数数组，长度较长）
  if (!Array.isArray(value)) return false
  if (value.length < 10) return false // 太短的数组不认为是 Embedding
  // 检查是否都是数字
  return value.every(item => typeof item === 'number')
}

const loadStats = async () => {
  try {
    const data = await getGraphStats()
    stats.value = data
  } catch (error) {
    message.error('获取统计信息失败: ' + error.message)
  }
}

const loadGraphData = async () => {
  try {
    const data = await getGraphData(200)
    graphData.value = data
  } catch (error) {
    console.error('获取图数据失败:', error)
  }
}

const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    message.warning('请输入实体名称')
    return
  }
  
  searching.value = true
  // 清除之前的高亮
  if (graphRef.value && graphRef.value.clearHighlight) {
    graphRef.value.clearHighlight()
  }
  
  try {
    // 解析输入：支持两种格式
    // 1. 两个实体名称（空格分隔）："马云 马化腾" -> 查找路径
    // 2. 单个实体名称："马云" -> 查找关系链
    const queryParts = searchQuery.value.trim().split(/\s+/)
    let sourceEntity = queryParts[0]
    let targetEntity = queryParts.length > 1 ? queryParts.slice(1).join(' ') : null
    
    // 调用路径查询API
    const result = await findPaths(sourceEntity, targetEntity, 10, 100)
    console.log('路径查询结果:', result)
    
    // 后端返回的是 PathQueryResponse 对象，包含 paths 数组
    const paths = result?.paths || []
    if (paths && Array.isArray(paths) && paths.length > 0) {
      // 提取所有路径中的节点ID和边ID
      const allHighlightedNodeIds = new Set()
      const allHighlightedEdgeIds = new Set()
      const shortestPathNodeIds = new Set()
      const shortestPathEdgeIds = new Set()
      
      paths.forEach((path) => {
        path.segments.forEach((segment) => {
          allHighlightedNodeIds.add(segment.source_id)
          allHighlightedNodeIds.add(segment.target_id)
          allHighlightedEdgeIds.add(segment.relation_id)
          
          // 如果是最短路径，单独记录
          if (path.is_shortest) {
            shortestPathNodeIds.add(segment.source_id)
            shortestPathNodeIds.add(segment.target_id)
            shortestPathEdgeIds.add(segment.relation_id)
          }
        })
      })
      
      // 调用图谱组件的高亮方法
      if (graphRef.value && graphRef.value.highlightPaths) {
        graphRef.value.highlightPaths(
          Array.from(allHighlightedNodeIds),
          Array.from(allHighlightedEdgeIds),
          Array.from(shortestPathNodeIds),
          Array.from(shortestPathEdgeIds)
        )
        
        const shortestCount = paths.filter(p => p.is_shortest).length
        message.success(
          `找到 ${paths.length} 条路径${shortestCount > 0 ? `，其中 ${shortestCount} 条为最短路径（已用更亮颜色标注）` : ''}`
        )
      } else {
        message.warning('图谱组件未就绪，请稍后重试')
      }
    } else {
      message.info('未找到相关路径')
      // 清除高亮
      if (graphRef.value && graphRef.value.clearHighlight) {
        graphRef.value.clearHighlight()
      }
    }
  } catch (error) {
    console.error('路径查询错误:', error)
    message.error('查询失败: ' + (error.response?.data?.detail || error.message))
    // 清除高亮
    if (graphRef.value && graphRef.value.clearHighlight) {
      graphRef.value.clearHighlight()
    }
  } finally {
    searching.value = false
  }
}

onMounted(() => {
  loadStats()
  loadGraphData()
})
</script>

