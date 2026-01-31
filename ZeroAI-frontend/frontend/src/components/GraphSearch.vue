<template>
  <div class="graph-search">
    <a-card title="图谱查找">
      <a-space direction="vertical" style="width: 100%" size="large">
        <!-- GroupID 选择区域（单GroupID模式） -->
        <a-card size="small" title="查询条件" v-if="props.mode !== 'composite'">
          <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
            <a-form-item label="GroupID">
              <a-space style="width: 100%">
                <a-auto-complete
                  v-model:value="selectedGroupId"
                  placeholder="选择或输入 GroupID"
                  style="flex: 1"
                  :options="groupIdOptions"
                  :loading="loadingDocuments"
                  allow-clear
                  @search="handleGroupIdSearch"
                  @change="handleGroupIdChange"
                  @select="handleGroupIdSelect"
                />
                <a-button type="primary" @click="loadGraphData" :loading="loading">
                  查询图谱
                </a-button>
              </a-space>
            </a-form-item>
            
            <!-- 版本筛选器 -->
            <a-form-item label="版本筛选" v-if="availableVersions.length > 0">
              <a-space>
                <a-checkbox-group v-model:value="selectedVersions" @change="handleVersionFilterChange">
                  <a-checkbox value="all">全部</a-checkbox>
                  <a-checkbox
                    v-for="version in availableVersions"
                    :key="version"
                    :value="version"
                  >
                    {{ version }}
                  </a-checkbox>
                </a-checkbox-group>
              </a-space>
            </a-form-item>
          </a-form>
        </a-card>
        
        <!-- 组合模式提示 -->
        <a-card size="small" v-if="props.mode === 'composite'">
          <a-alert
            :message="props.compositeUuid ? '组合图谱查询模式' : '多GroupID查询模式'"
            :description="props.compositeUuid ? `正在查询组合: ${props.compositeUuid}` : `正在查询 ${props.groupIds.length} 个GroupID`"
            type="info"
            show-icon
          />
        </a-card>

        <!-- 统计信息卡片 -->
        <a-row :gutter="16" v-if="statistics.totalNodes > 0">
          <a-col :span="6">
            <a-statistic
              title="节点总数"
              :value="statistics.totalNodes"
              :value-style="{ color: '#1890ff' }"
            >
              <template #suffix>
                <span style="font-size: 14px; color: #666">
                  ({{ filteredNodes.length }} 已筛选)
                </span>
              </template>
            </a-statistic>
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="关系总数"
              :value="statistics.totalRelationships"
              :value-style="{ color: '#52c41a' }"
            >
              <template #suffix>
                <span style="font-size: 14px; color: #666">
                  ({{ filteredRelationships.length }} 已筛选)
                </span>
              </template>
            </a-statistic>
          </a-col>
          <a-col :span="12">
            <a-card size="small" title="版本统计">
              <a-space>
                <a-tag
                  v-for="(count, version) in statistics.byVersion"
                  :key="version"
                  :color="getVersionColor(version)"
                >
                  {{ version }}: {{ count.nodes }}节点 / {{ count.relationships }}关系
                </a-tag>
              </a-space>
            </a-card>
          </a-col>
        </a-row>
        
        <!-- GroupID统计（组合模式） -->
        <a-row :gutter="16" v-if="graphData.statistics && graphData.statistics.by_group_id">
          <a-col :span="24">
            <a-card size="small" title="按GroupID统计">
              <a-space wrap>
                <a-tag
                  v-for="(stats, groupId) in graphData.statistics.by_group_id"
                  :key="groupId"
                  color="blue"
                >
                  {{ groupId }}: {{ stats.nodes }}节点 / {{ stats.edges }}关系
                </a-tag>
              </a-space>
            </a-card>
          </a-col>
        </a-row>

        <!-- 主内容区域 - Tab切换 -->
        <a-tabs v-model:activeKey="activeTab" v-if="graphData.nodes.length > 0">
          <!-- 节点列表 -->
          <a-tab-pane key="nodes" tab="节点列表">
            <a-space direction="vertical" style="width: 100%">
              <a-space>
                <a-input-search
                  v-model:value="nodeSearchText"
                  placeholder="搜索节点名称"
                  style="width: 300px"
                  @search="handleNodeSearch"
                />
                <a-select
                  v-model:value="nodeTypeFilter"
                  placeholder="筛选节点类型"
                  style="width: 200px"
                  allow-clear
                  @change="handleNodeTypeFilterChange"
                >
                  <a-select-option value="">全部类型</a-select-option>
                  <a-select-option
                    v-for="type in nodeTypes"
                    :key="type"
                    :value="type"
                  >
                    {{ type }}
                  </a-select-option>
                </a-select>
              </a-space>
              
              <a-table
                :columns="nodeColumns"
                :data-source="filteredNodes"
                :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }"
                row-key="id"
                size="small"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'version'">
                    <a-tag :color="getVersionColor(record.version)">
                      {{ record.version || '未知' }}
                    </a-tag>
                  </template>
                  <template v-if="column.key === 'type'">
                    <a-tag>{{ record.type }}</a-tag>
                  </template>
                  <template v-if="column.key === 'labels'">
                    <a-space>
                      <a-tag
                        v-for="label in record.labels"
                        :key="label"
                        color="blue"
                      >
                        {{ label }}
                      </a-tag>
                    </a-space>
                  </template>
                  <template v-if="column.key === 'source'">
                    <a-space>
                      <a-tag
                        v-for="sourceId in (record.source_group_ids || [record.source_group_id])"
                        :key="sourceId"
                        color="cyan"
                      >
                        {{ sourceId }}
                      </a-tag>
                    </a-space>
                  </template>
                  <template v-if="column.key === 'action'">
                    <a-button type="link" size="small" @click="viewNodeDetail(record)">
                      查看详情
                    </a-button>
                  </template>
                </template>
              </a-table>
            </a-space>
          </a-tab-pane>

          <!-- 关系列表 -->
          <a-tab-pane key="relationships" tab="关系列表">
            <a-space direction="vertical" style="width: 100%">
              <a-space>
                <a-input-search
                  v-model:value="relationshipSearchText"
                  placeholder="搜索关系"
                  style="width: 300px"
                  @search="handleRelationshipSearch"
                />
                <a-select
                  v-model:value="relationshipTypeFilter"
                  placeholder="筛选关系类型"
                  style="width: 200px"
                  allow-clear
                  @change="handleRelationshipTypeFilterChange"
                >
                  <a-select-option value="">全部类型</a-select-option>
                  <a-select-option
                    v-for="type in relationshipTypes"
                    :key="type"
                    :value="type"
                  >
                    {{ type }}
                  </a-select-option>
                </a-select>
              </a-space>
              
              <a-table
                :columns="relationshipColumns"
                :data-source="filteredRelationships"
                :pagination="{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }"
                row-key="id"
                size="small"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'version'">
                    <a-tag :color="getVersionColor(record.version)">
                      {{ record.version || '未知' }}
                    </a-tag>
                  </template>
                  <template v-if="column.key === 'type'">
                    <a-tag color="purple">{{ record.type }}</a-tag>
                  </template>
                  <template v-if="column.key === 'source'">
                    <a-tag color="cyan">{{ record.source_group_id || '未知' }}</a-tag>
                  </template>
                  <template v-if="column.key === 'action'">
                    <a-button type="link" size="small" @click="viewRelationshipDetail(record)">
                      查看详情
                    </a-button>
                  </template>
                </template>
              </a-table>
            </a-space>
          </a-tab-pane>

          <!-- 图谱可视化 -->
          <a-tab-pane key="visualization" tab="图谱可视化">
            <div style="position: relative; width: 100%; height: calc(100vh - 400px); min-height: 600px">
              <GraphVisualization
                v-if="graphData.nodes.length > 0"
                :data="visualizationData"
                @nodeClick="handleVisualizationNodeClick"
                @edgeClick="handleVisualizationEdgeClick"
              />
              <a-empty v-else description="暂无数据，请先查询图谱" />
            </div>
          </a-tab-pane>

          <!-- 版本对比 -->
          <a-tab-pane key="compare" tab="版本对比">
            <a-space direction="vertical" style="width: 100%">
              <a-card size="small">
                <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
                  <a-form-item label="对比版本">
                    <a-space>
                      <a-select
                        v-model:value="compareVersion1"
                        placeholder="选择版本1"
                        style="width: 150px"
                        :options="versionOptions"
                      />
                      <span>vs</span>
                      <a-select
                        v-model:value="compareVersion2"
                        placeholder="选择版本2"
                        style="width: 150px"
                        :options="versionOptions"
                      />
                      <a-button type="primary" @click="compareVersions" :loading="comparing">
                        开始对比
                      </a-button>
                    </a-space>
                  </a-form-item>
                </a-form>
              </a-card>

              <!-- 对比结果 -->
              <div v-if="compareResult">
                <a-row :gutter="16" style="margin-bottom: 16px">
                  <a-col :span="12">
                    <a-card size="small" :title="`${compareResult.version1?.version || '版本1'} 统计`" :head-style="{ backgroundColor: '#e6f7ff' }">
                      <a-statistic-group>
                        <a-statistic title="节点数" :value="compareResult.version1?.entity_count || 0" />
                        <a-statistic title="关系数" :value="compareResult.version1?.relationship_count || 0" />
                      </a-statistic-group>
                    </a-card>
                  </a-col>
                  <a-col :span="12">
                    <a-card size="small" :title="`${compareResult.version2?.version || '版本2'} 统计`" :head-style="{ backgroundColor: '#f6ffed' }">
                      <a-statistic-group>
                        <a-statistic title="节点数" :value="compareResult.version2?.entity_count || 0" />
                        <a-statistic title="关系数" :value="compareResult.version2?.relationship_count || 0" />
                      </a-statistic-group>
                    </a-card>
                  </a-col>
                </a-row>

                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-card size="small" title="实体变化">
                      <a-space direction="vertical" style="width: 100%">
                        <div>
                          <a-tag color="green">新增: {{ compareResult.entity_changes?.added?.length || 0 }}</a-tag>
                          <a-tag color="red">删除: {{ compareResult.entity_changes?.removed?.length || 0 }}</a-tag>
                          <a-tag color="orange">修改: {{ compareResult.entity_changes?.modified?.length || 0 }}</a-tag>
                        </div>
                        <a-collapse>
                          <a-collapse-panel v-if="compareResult.entity_changes?.added?.length > 0" key="added" header="新增实体">
                            <a-list
                              :data-source="compareResult.entity_changes.added"
                              size="small"
                            >
                              <template #renderItem="{ item }">
                                <a-list-item>
                                  <a-tag>{{ item.type || 'Entity' }}</a-tag>
                                  {{ item.name }}
                                </a-list-item>
                              </template>
                            </a-list>
                          </a-collapse-panel>
                          <a-collapse-panel v-if="compareResult.entity_changes?.removed?.length > 0" key="removed" header="删除实体">
                            <a-list
                              :data-source="compareResult.entity_changes.removed"
                              size="small"
                            >
                              <template #renderItem="{ item }">
                                <a-list-item>
                                  <a-tag>{{ item.type || 'Entity' }}</a-tag>
                                  {{ item.name }}
                                </a-list-item>
                              </template>
                            </a-list>
                          </a-collapse-panel>
                        </a-collapse>
                      </a-space>
                    </a-card>
                  </a-col>
                  <a-col :span="12">
                    <a-card size="small" title="关系变化">
                      <a-space direction="vertical" style="width: 100%">
                        <div>
                          <a-tag color="green">新增: {{ compareResult.relationship_changes?.added?.length || 0 }}</a-tag>
                          <a-tag color="red">删除: {{ compareResult.relationship_changes?.removed?.length || 0 }}</a-tag>
                          <a-tag color="orange">修改: {{ compareResult.relationship_changes?.modified?.length || 0 }}</a-tag>
                        </div>
                        <a-collapse>
                          <a-collapse-panel v-if="compareResult.relationship_changes?.added?.length > 0" key="added" header="新增关系">
                            <a-list
                              :data-source="compareResult.relationship_changes.added"
                              size="small"
                            >
                              <template #renderItem="{ item }">
                                <a-list-item>
                                  {{ item.source_name }} --[{{ item.type }}]--> {{ item.target_name }}
                                </a-list-item>
                              </template>
                            </a-list>
                          </a-collapse-panel>
                          <a-collapse-panel v-if="compareResult.relationship_changes?.removed?.length > 0" key="removed" header="删除关系">
                            <a-list
                              :data-source="compareResult.relationship_changes.removed"
                              size="small"
                            >
                              <template #renderItem="{ item }">
                                <a-list-item>
                                  {{ item.source_name }} --[{{ item.type }}]--> {{ item.target_name }}
                                </a-list-item>
                              </template>
                            </a-list>
                          </a-collapse-panel>
                        </a-collapse>
                      </a-space>
                    </a-card>
                  </a-col>
                </a-row>

                <a-card size="small" style="margin-top: 16px" v-if="compareResult.similarity_score !== undefined">
                  <a-statistic
                    title="相似度"
                    :value="(compareResult.similarity_score * 100).toFixed(2)"
                    suffix="%"
                    :value-style="{ color: '#1890ff', fontSize: '24px' }"
                  />
                </a-card>
              </div>
            </a-space>
          </a-tab-pane>
        </a-tabs>

        <!-- 空状态 -->
        <a-empty
          v-if="!loading && graphData.nodes.length === 0 && (selectedGroupId || props.mode === 'composite')"
          :description="props.mode === 'composite' ? '暂无数据' : '暂无数据，请先选择 GroupID 并查询'"
        />
      </a-space>
    </a-card>

    <!-- 节点详情抽屉 -->
    <a-drawer
      v-model:open="nodeDetailVisible"
      title="节点详情"
      width="600px"
      placement="right"
    >
      <a-descriptions
        v-if="selectedNode"
        :column="1"
        bordered
      >
        <a-descriptions-item label="ID">{{ selectedNode.id }}</a-descriptions-item>
        <a-descriptions-item label="名称">{{ selectedNode.name }}</a-descriptions-item>
        <a-descriptions-item label="类型">
          <a-tag>{{ selectedNode.type }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="标签">
          <a-space>
            <a-tag v-for="label in selectedNode.labels" :key="label" color="blue">
              {{ label }}
            </a-tag>
          </a-space>
        </a-descriptions-item>
        <a-descriptions-item label="版本">
          <a-tag :color="getVersionColor(selectedNode.version)">
            {{ selectedNode.version || '未知' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="属性">
          <pre style="max-height: 300px; overflow: auto">{{ JSON.stringify(selectedNode.properties, null, 2) }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>

    <!-- 节点属性面板（图谱可视化专用） -->
    <a-drawer
      v-model:open="nodePropertyDrawerVisible"
      title="节点属性"
      width="400px"
      placement="right"
      :closable="true"
    >
      <a-descriptions
        v-if="selectedVisualizationNode"
        :column="1"
        bordered
        size="small"
      >
        <a-descriptions-item label="ID">
          {{ selectedVisualizationNode.id }}
        </a-descriptions-item>
        <a-descriptions-item label="名称">
          {{ selectedVisualizationNode.name || selectedVisualizationNode.properties?.name || '未命名' }}
        </a-descriptions-item>
        <a-descriptions-item label="类型">
          <a-tag>{{ selectedVisualizationNode.type || (selectedVisualizationNode.labels && selectedVisualizationNode.labels[0]) || 'Entity' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="所有标签">
          <a-space>
            <a-tag
              v-for="label in (selectedVisualizationNode.labels || [])"
              :key="label"
              color="blue"
            >
              {{ label }}
            </a-tag>
          </a-space>
        </a-descriptions-item>
        <a-descriptions-item label="版本" v-if="selectedVisualizationNode.version">
          <a-tag :color="getVersionColor(selectedVisualizationNode.version)">
            {{ selectedVisualizationNode.version }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="来源" v-if="selectedVisualizationNode.source_group_id">
          <a-tag color="cyan">{{ selectedVisualizationNode.source_group_id }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建时间" v-if="selectedVisualizationNode.properties?.created_at">
          {{ formatDateTime(selectedVisualizationNode.properties.created_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="其他属性">
          <pre style="max-height: 400px; overflow: auto; font-size: 12px; white-space: pre-wrap; word-wrap: break-word">
{{ formatNodeProperties(selectedVisualizationNode) }}
          </pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>

    <!-- 关系详情抽屉 -->
    <a-drawer
      v-model:open="relationshipDetailVisible"
      title="关系详情"
      width="600px"
      placement="right"
    >
      <a-descriptions
        v-if="selectedRelationship"
        :column="1"
        bordered
      >
        <a-descriptions-item label="ID">{{ selectedRelationship.id }}</a-descriptions-item>
        <a-descriptions-item label="类型">
          <a-tag color="purple">{{ selectedRelationship.type }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="源节点">{{ selectedRelationship.sourceName }}</a-descriptions-item>
        <a-descriptions-item label="目标节点">{{ selectedRelationship.targetName }}</a-descriptions-item>
        <a-descriptions-item label="版本">
          <a-tag :color="getVersionColor(selectedRelationship.version)">
            {{ selectedRelationship.version || '未知' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="属性">
          <pre style="max-height: 300px; overflow: auto">{{ JSON.stringify(selectedRelationship.properties, null, 2) }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { getDocumentList, getDocumentGraph, compareDocumentVersions } from '../api/wordDocument'
import { getCompositeGraph } from '../api/composite'
import GraphVisualization from './GraphVisualization.vue'

// Props
const props = defineProps({
  compositeUuid: {
    type: String,
    default: null
  },
  groupIds: {
    type: Array,
    default: () => []
  },
  mode: {
    type: String,
    default: 'single'  // 'single' 或 'composite'
  }
})

// 数据状态
const selectedGroupId = ref('')
const loading = ref(false)
const loadingDocuments = ref(false)
const documentOptions = ref([])
const graphData = ref({ nodes: [], edges: [], document_id: '', statistics: null })

// 版本筛选
const availableVersions = ref([])
const selectedVersions = ref(['all'])

// 节点筛选
const nodeSearchText = ref('')
const nodeTypeFilter = ref('')
const nodeTypes = ref([])

// 关系筛选
const relationshipSearchText = ref('')
const relationshipTypeFilter = ref('')
const relationshipTypes = ref([])

// Tab切换
const activeTab = ref('nodes')

// 版本对比
const compareVersion1 = ref(null)
const compareVersion2 = ref(null)
const comparing = ref(false)
const compareResult = ref(null)

// 详情抽屉
const nodeDetailVisible = ref(false)
const relationshipDetailVisible = ref(false)
const selectedNode = ref(null)
const selectedRelationship = ref(null)

// 图谱可视化节点属性面板
const nodePropertyDrawerVisible = ref(false)
const selectedVisualizationNode = ref(null)

// 统计信息
const statistics = computed(() => {
  const stats = {
    totalNodes: graphData.value.nodes.length,
    totalRelationships: graphData.value.edges.length,
    byVersion: {}
  }

  // 统计各版本的节点和关系数
  graphData.value.nodes.forEach(node => {
    const version = node.version || '未知'
    if (!stats.byVersion[version]) {
      stats.byVersion[version] = { nodes: 0, relationships: 0 }
    }
    stats.byVersion[version].nodes++
  })

  graphData.value.edges.forEach(edge => {
    const version = edge.version || '未知'
    if (!stats.byVersion[version]) {
      stats.byVersion[version] = { nodes: 0, relationships: 0 }
    }
    stats.byVersion[version].relationships++
  })

  return stats
})

// 过滤后的节点
const filteredNodes = computed(() => {
  let nodes = graphData.value.nodes

  // 版本筛选
  if (!selectedVersions.value.includes('all') && selectedVersions.value.length > 0) {
    nodes = nodes.filter(node => {
      const nodeVersion = node.version || '未知'
      return selectedVersions.value.includes(nodeVersion)
    })
  }

  // 搜索筛选
  if (nodeSearchText.value) {
    const searchLower = nodeSearchText.value.toLowerCase()
    nodes = nodes.filter(node => {
      const name = (node.name || '').toLowerCase()
      return name.includes(searchLower)
    })
  }

  // 类型筛选
  if (nodeTypeFilter.value) {
    nodes = nodes.filter(node => node.type === nodeTypeFilter.value)
  }

  return nodes
})

// 过滤后的关系
const filteredRelationships = computed(() => {
  let edges = graphData.value.edges

  // 版本筛选
  if (!selectedVersions.value.includes('all') && selectedVersions.value.length > 0) {
    edges = edges.filter(edge => {
      const edgeVersion = edge.version || '未知'
      return selectedVersions.value.includes(edgeVersion)
    })
  }

  // 搜索筛选
  if (relationshipSearchText.value) {
    const searchLower = relationshipSearchText.value.toLowerCase()
    edges = edges.filter(edge => {
      const sourceName = (edge.sourceName || '').toLowerCase()
      const targetName = (edge.targetName || '').toLowerCase()
      const type = (edge.type || '').toLowerCase()
      return sourceName.includes(searchLower) || 
             targetName.includes(searchLower) || 
             type.includes(searchLower)
    })
  }

  // 类型筛选
  if (relationshipTypeFilter.value) {
    edges = edges.filter(edge => edge.type === relationshipTypeFilter.value)
  }

  return edges
})

// 版本选项（用于对比）
const versionOptions = computed(() => {
  return availableVersions.value.map(v => ({ label: v, value: v }))
})

// 可视化数据（格式化给GraphVisualization组件）
const visualizationData = computed(() => {
  if (!graphData.value.nodes.length) {
    return null
  }
  
  // 格式化节点数据
  const nodes = graphData.value.nodes.map(node => ({
    id: String(node.id),
    name: node.name || node.properties?.name || '未命名',
    labels: node.labels || [node.type || 'Entity'],
    properties: node.properties || {},
    type: node.type || (node.labels && node.labels[0]) || 'Entity',
    content: node.content,
    version: node.version,
    source_group_id: node.source_group_id
  }))
  
  // 格式化边数据
  const edges = graphData.value.edges.map(edge => ({
    id: String(edge.id),
    source: String(edge.source),
    target: String(edge.target),
    type: edge.type || 'RELATES_TO',
    properties: edge.properties || {},
    name: edge.type,
    version: edge.version,
    source_group_id: edge.source_group_id
  }))
  
  return { nodes, edges }
})

// GroupID选项（用于自动完成）
const groupIdOptions = computed(() => {
  return documentOptions.value.map(doc => ({
    value: doc.document_id,
    label: `${doc.document_name} (${doc.document_id})`
  }))
})

// 表格列定义
const nodeColumns = computed(() => {
  const baseColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '类型', key: 'type', width: 120 },
    { title: '标签', key: 'labels', width: 200 },
    { title: '版本', key: 'version', width: 100 }
  ]
  
  // 如果是组合模式，添加来源列
  if (props.mode === 'composite' || graphData.value.statistics) {
    baseColumns.push({ title: '来源', key: 'source', width: 150 })
  }
  
  baseColumns.push({ title: '操作', key: 'action', width: 100 })
  return baseColumns
})

const relationshipColumns = computed(() => {
  const baseColumns = [
    { title: '源节点', dataIndex: 'sourceName', key: 'sourceName', ellipsis: true },
    { title: '关系类型', key: 'type', width: 150 },
    { title: '目标节点', dataIndex: 'targetName', key: 'targetName', ellipsis: true },
    { title: '版本', key: 'version', width: 100 }
  ]
  
  // 如果是组合模式，添加来源列
  if (props.mode === 'composite' || graphData.value.statistics) {
    baseColumns.push({ title: '来源', key: 'source', width: 150 })
  }
  
  baseColumns.push({ title: '操作', key: 'action', width: 100 })
  return baseColumns
})

// 方法
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

const loadGraphData = async () => {
  // 如果是组合模式，使用组合查询
  if (props.mode === 'composite' && props.compositeUuid) {
    await loadCompositeGraph()
    return
  }
  
  // 如果是多GroupID模式
  if (props.mode === 'composite' && props.groupIds && props.groupIds.length > 0) {
    await loadMultipleGroupIdsGraph()
    return
  }
  
  // 单GroupID模式
  if (!selectedGroupId.value) {
    message.warning('请先选择或输入 GroupID')
    return
  }

  loading.value = true
  try {
    const response = await getDocumentGraph(selectedGroupId.value, 'qianwen', 2000)
    
    if (response) {
      // 处理节点数据，提取版本信息
      // 先创建一个Episode节点到版本的映射
      const episodeVersionMap = new Map()
      const nodes = (response.nodes || []).map(node => {
        const props = node.properties || {}
        const labels = node.labels || []
        const isEpisodic = labels.includes('Episodic')
        
        // Episode节点直接有version属性
        let version = props.version || '未知'
        if (isEpisodic && version !== '未知') {
          episodeVersionMap.set(node.id, version)
        }
        
        return {
          ...node,
          version: version,
          name: props.name || node.name || '未命名',
          type: labels[0] || 'Entity',
          isEpisodic: isEpisodic
        }
      })
      
      // 对于Entity节点，如果没有version，尝试通过关系查找关联的Episode
      nodes.forEach(node => {
        if (!node.isEpisodic && node.version === '未知') {
          // 查找与该Entity关联的Episode节点（通过关系）
          const relatedEpisodes = response.edges
            .filter(edge => (edge.source === node.id || edge.target === node.id) && 
                           edge.type === 'MENTIONS')
            .map(edge => {
              const sourceNode = nodes.find(n => n.id === edge.source)
              const targetNode = nodes.find(n => n.id === edge.target)
              return sourceNode?.isEpisodic ? sourceNode : (targetNode?.isEpisodic ? targetNode : null)
            })
            .filter(n => n !== null)
          
          if (relatedEpisodes.length > 0) {
            // 使用第一个关联Episode的版本
            const episodeVersion = relatedEpisodes[0].version
            if (episodeVersion !== '未知') {
              node.version = episodeVersion
            }
          }
        }
      })

      // 处理关系数据，提取版本信息
      const edges = (response.edges || []).map(edge => {
        const props = edge.properties || {}
        let version = props.version || '未知'
        
        // 如果关系没有version，尝试从源节点或目标节点获取
        if (version === '未知') {
          const sourceNode = nodes.find(n => n.id === edge.source)
          const targetNode = nodes.find(n => n.id === edge.target)
          
          // 优先使用Episode节点的版本
          if (sourceNode?.isEpisodic && sourceNode.version !== '未知') {
            version = sourceNode.version
          } else if (targetNode?.isEpisodic && targetNode.version !== '未知') {
            version = targetNode.version
          } else if (sourceNode?.version !== '未知') {
            version = sourceNode.version
          } else if (targetNode?.version !== '未知') {
            version = targetNode.version
          }
        }
        
        // 查找源节点和目标节点名称
        const sourceNode = nodes.find(n => n.id === edge.source)
        const targetNode = nodes.find(n => n.id === edge.target)
        
        return {
          ...edge,
          version: version,
          sourceName: sourceNode?.name || `节点${edge.source}`,
          targetName: targetNode?.name || `节点${edge.target}`
        }
      })

      graphData.value = {
        nodes,
        edges,
        document_id: response.document_id || selectedGroupId.value,
        statistics: null
      }

      // 提取可用版本
      const versions = new Set()
      nodes.forEach(node => {
        if (node.version && node.version !== '未知') {
          versions.add(node.version)
        }
      })
      edges.forEach(edge => {
        if (edge.version && edge.version !== '未知') {
          versions.add(edge.version)
        }
      })
      availableVersions.value = Array.from(versions).sort()
      selectedVersions.value = ['all'] // 默认显示全部

      // 提取节点类型
      const types = new Set()
      nodes.forEach(node => {
        if (node.type) {
          types.add(node.type)
        }
      })
      nodeTypes.value = Array.from(types).sort()

      // 提取关系类型
      const relTypes = new Set()
      edges.forEach(edge => {
        if (edge.type) {
          relTypes.add(edge.type)
        }
      })
      relationshipTypes.value = Array.from(relTypes).sort()

      message.success(`成功加载 ${nodes.length} 个节点和 ${edges.length} 个关系`)
    }
  } catch (error) {
    console.error('加载图谱数据失败:', error)
    message.error(`加载失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

// 加载组合图谱数据
const loadCompositeGraph = async () => {
  if (!props.compositeUuid) {
    message.warning('组合UUID不存在')
    return
  }

  loading.value = true
  try {
    const response = await getCompositeGraph(props.compositeUuid, 2000)
    
    if (response) {
      // 处理节点数据
      const nodes = (response.nodes || []).map(node => {
        const props = node.properties || {}
        const labels = node.labels || []
        
        return {
          ...node,
          version: props.version || '未知',
          name: props.name || node.name || '未命名',
          type: labels[0] || 'Entity',
          source_group_id: node.source_group_id || '未知',
          source_group_ids: node.source_group_ids || [node.source_group_id || '未知']
        }
      })

      // 处理关系数据
      const edges = (response.edges || []).map(edge => {
        const props = edge.properties || {}
        
        // 查找源节点和目标节点名称
        const sourceNode = nodes.find(n => n.id === edge.source)
        const targetNode = nodes.find(n => n.id === edge.target)
        
        return {
          ...edge,
          version: props.version || '未知',
          sourceName: sourceNode?.name || `节点${edge.source}`,
          targetName: targetNode?.name || `节点${edge.target}`,
          source_group_id: edge.source_group_id || '未知'
        }
      })

      graphData.value = {
        nodes,
        edges,
        document_id: props.compositeUuid,
        statistics: response.statistics || null
      }

      // 提取可用版本
      const versions = new Set()
      nodes.forEach(node => {
        if (node.version && node.version !== '未知') {
          versions.add(node.version)
        }
      })
      edges.forEach(edge => {
        if (edge.version && edge.version !== '未知') {
          versions.add(edge.version)
        }
      })
      availableVersions.value = Array.from(versions).sort()
      selectedVersions.value = ['all']

      // 提取节点类型和关系类型
      const types = new Set()
      nodes.forEach(node => {
        if (node.type) {
          types.add(node.type)
        }
      })
      nodeTypes.value = Array.from(types).sort()

      const relTypes = new Set()
      edges.forEach(edge => {
        if (edge.type) {
          relTypes.add(edge.type)
        }
      })
      relationshipTypes.value = Array.from(relTypes).sort()

      message.success(`成功加载 ${nodes.length} 个节点和 ${edges.length} 个关系`)
    }
  } catch (error) {
    console.error('加载组合图谱数据失败:', error)
    message.error(`加载失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

// 加载多个GroupID的图谱数据
const loadMultipleGroupIdsGraph = async () => {
  if (!props.groupIds || props.groupIds.length === 0) {
    message.warning('GroupID列表为空')
    return
  }

  loading.value = true
  try {
    // 并行查询所有GroupID的数据
    const results = await Promise.all(
      props.groupIds.map(groupId => getDocumentGraph(groupId, 'qianwen', 2000))
    )
    
    // 合并数据并标记来源
    const allNodes = []
    const allEdges = []
    const nodeIdMap = {}
    const statistics = {
      by_group_id: {}
    }
    
    results.forEach((response, index) => {
      const groupId = props.groupIds[index]
      statistics.by_group_id[groupId] = { nodes: 0, edges: 0 }
      
      if (response) {
        // 处理节点
        const nodes = (response.nodes || []).map(node => {
          const props = node.properties || {}
          const labels = node.labels || []
          
          return {
            ...node,
            version: props.version || '未知',
            name: props.name || node.name || '未命名',
            type: labels[0] || 'Entity',
            source_group_id: groupId,
            source_group_ids: [groupId]
          }
        })
        
        // 处理边
        const edges = (response.edges || []).map(edge => {
          const props = edge.properties || {}
          
          return {
            ...edge,
            version: props.version || '未知',
            source_group_id: groupId
          }
        })
        
        // 合并节点（去重）
        nodes.forEach(node => {
          const nodeId = node.id
          if (nodeId in nodeIdMap) {
            // 节点已存在，添加来源信息
            const existing = nodeIdMap[nodeId]
            if (!existing.source_group_ids.includes(groupId)) {
              existing.source_group_ids.push(groupId)
            }
            statistics.by_group_id[groupId].nodes++
          } else {
            // 新节点
            nodeIdMap[nodeId] = node
            allNodes.push(node)
            statistics.by_group_id[groupId].nodes++
          }
        })
        
        // 合并边
        edges.forEach(edge => {
          const sourceId = edge.source
          const targetId = edge.target
          
          if (sourceId in nodeIdMap && targetId in nodeIdMap) {
            // 查找源节点和目标节点名称
            const sourceNode = nodeIdMap[sourceId]
            const targetNode = nodeIdMap[targetId]
            
            edge.sourceName = sourceNode.name
            edge.targetName = targetNode.name
            allEdges.push(edge)
            statistics.by_group_id[groupId].edges++
          }
        })
      }
    })
    
    graphData.value = {
      nodes: allNodes,
      edges: allEdges,
      document_id: props.groupIds.join(','),
      statistics: {
        total_nodes: allNodes.length,
        total_edges: allEdges.length,
        by_group_id: statistics.by_group_id
      }
    }
    
    // 提取版本、节点类型、关系类型
    const versions = new Set()
    allNodes.forEach(node => {
      if (node.version && node.version !== '未知') {
        versions.add(node.version)
      }
    })
    availableVersions.value = Array.from(versions).sort()
    selectedVersions.value = ['all']
    
    const types = new Set()
    allNodes.forEach(node => {
      if (node.type) {
        types.add(node.type)
      }
    })
    nodeTypes.value = Array.from(types).sort()
    
    const relTypes = new Set()
    allEdges.forEach(edge => {
      if (edge.type) {
        relTypes.add(edge.type)
      }
    })
    relationshipTypes.value = Array.from(relTypes).sort()
    
    message.success(`成功加载 ${allNodes.length} 个节点和 ${allEdges.length} 个关系`)
  } catch (error) {
    console.error('加载多GroupID图谱数据失败:', error)
    message.error(`加载失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

const handleGroupIdChange = () => {
  // GroupID改变时清空数据
  graphData.value = { nodes: [], edges: [], document_id: '' }
  availableVersions.value = []
  selectedVersions.value = ['all']
  compareResult.value = null
}

const handleVersionFilterChange = () => {
  // 版本筛选改变时，如果选择了"全部"，则只保留"全部"
  if (selectedVersions.value.includes('all')) {
    selectedVersions.value = ['all']
  }
}

const handleNodeSearch = () => {
  // 搜索已通过computed自动处理
}

const handleNodeTypeFilterChange = () => {
  // 类型筛选已通过computed自动处理
}

const handleRelationshipSearch = () => {
  // 搜索已通过computed自动处理
}

const handleRelationshipTypeFilterChange = () => {
  // 类型筛选已通过computed自动处理
}

const filterGroupIdOption = (input, option) => {
  const value = option.value || ''
  const label = option.children || ''
  return value.toLowerCase().includes(input.toLowerCase()) || 
         label.toLowerCase().includes(input.toLowerCase())
}

const handleGroupIdSearch = (value) => {
  // 允许用户输入自定义GroupID，这里可以添加搜索过滤逻辑
  // 如果需要，可以在这里过滤选项
}

const handleGroupIdSelect = (value) => {
  // 当用户从下拉列表中选择时触发
  selectedGroupId.value = value
}

const compareVersions = async () => {
  if (!compareVersion1.value || !compareVersion2.value) {
    message.warning('请选择两个版本进行对比')
    return
  }

  if (compareVersion1.value === compareVersion2.value) {
    message.warning('请选择不同的版本进行对比')
    return
  }

  if (!selectedGroupId.value) {
    message.warning('请先选择 GroupID')
    return
  }

  comparing.value = true
  try {
    const response = await compareDocumentVersions(
      selectedGroupId.value,
      compareVersion1.value,
      compareVersion2.value,
      'qianwen'
    )
    
    if (response) {
      compareResult.value = response
      message.success('版本对比完成')
    }
  } catch (error) {
    console.error('版本对比失败:', error)
    message.error(`对比失败: ${error.message || error}`)
  } finally {
    comparing.value = false
  }
}

const viewNodeDetail = (node) => {
  selectedNode.value = node
  nodeDetailVisible.value = true
}

const viewRelationshipDetail = (relationship) => {
  selectedRelationship.value = relationship
  relationshipDetailVisible.value = true
}

const getVersionColor = (version) => {
  const colorMap = {
    'V1': 'blue',
    'V2': 'green',
    'V3': 'orange',
    'V4': 'purple',
    'V5': 'cyan'
  }
  return colorMap[version] || 'default'
}

// 处理图谱可视化节点点击
const handleVisualizationNodeClick = (node) => {
  selectedVisualizationNode.value = node
  nodePropertyDrawerVisible.value = true
}

// 处理图谱可视化边点击
const handleVisualizationEdgeClick = (edge) => {
  // 查找对应的关系数据
  const relationship = graphData.value.edges.find(e => e.id === edge.id)
  if (relationship) {
    viewRelationshipDetail(relationship)
  }
}

// 格式化日期时间
const formatDateTime = (dateValue) => {
  if (!dateValue) return '-'
  try {
    const date = new Date(dateValue)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (e) {
    return String(dateValue)
  }
}

// 格式化节点属性（用于显示）
const formatNodeProperties = (node) => {
  if (!node) return ''
  
  const props = node.properties || {}
  const result = {}
  
  // 排除已显示的属性
  const excludeKeys = ['name', 'version', 'created_at', 'updated_at', 'id', 'uuid', 'group_id', 'source_group_id']
  
  for (const [key, value] of Object.entries(props)) {
    if (!excludeKeys.includes(key)) {
      // 如果是对象或数组，格式化为JSON字符串
      if (typeof value === 'object' && value !== null) {
        result[key] = JSON.stringify(value, null, 2)
      } else {
        result[key] = value
      }
    }
  }
  
  // 如果有content属性，单独显示
  if (node.content) {
    result['内容'] = node.content
  }
  
  // 如果有summary属性，单独显示
  if (props.summary) {
    result['摘要'] = props.summary
  }
  
  if (Object.keys(result).length === 0) {
    return '无其他属性'
  }
  
  // 格式化为易读的文本
  return Object.entries(result)
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n\n')
}

// 监听props变化，自动加载组合数据
watch(() => [props.compositeUuid, props.groupIds, props.mode], () => {
  if (props.mode === 'composite') {
    if (props.compositeUuid) {
      loadCompositeGraph()
    } else if (props.groupIds && props.groupIds.length > 0) {
      loadMultipleGroupIdsGraph()
    }
  }
}, { immediate: true })

onMounted(() => {
  loadDocuments()
  
  // 如果是组合模式，自动加载数据
  if (props.mode === 'composite') {
    if (props.compositeUuid) {
      loadCompositeGraph()
    } else if (props.groupIds && props.groupIds.length > 0) {
      loadMultipleGroupIdsGraph()
    }
  }
})
</script>

<style scoped>
.graph-search {
  padding: 16px;
}

:deep(.ant-statistic-group) {
  display: flex;
  gap: 24px;
}
</style>

