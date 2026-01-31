<template>
  <div class="document-management">
    <a-card title="文档管理">
      <a-table
        :columns="columns"
        :data-source="documents"
        :loading="loading"
        :pagination="pagination"
        row-key="document_id"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleView(record)">
                查看详情
              </a-button>
              <a-button type="link" size="small" @click="handleViewEpisodes(record)">
                查看 Episode
              </a-button>
              <a-button type="link" size="small" @click="handleViewGraph(record)">
                查看图谱
              </a-button>
              <a-button type="link" size="small" @click="handleViewVersions(record)">
                查看版本
              </a-button>
              <a-button type="link" size="small" danger @click="handleDelete(record)">
                删除
              </a-button>
            </a-space>
          </template>
          <template v-if="column.key === 'version'">
            <a-tag v-if="record.statistics?.version" color="blue">
              {{ record.statistics.version }}
            </a-tag>
            <span v-else style="color: #999">-</span>
          </template>
          <template v-if="column.key === 'statistics'">
            <a-space>
              <a-tag color="blue">{{ record.statistics?.total_sections || 0 }} 章节</a-tag>
              <a-tag color="green">{{ record.statistics?.total_images || 0 }} 图片</a-tag>
              <a-tag color="orange">{{ record.statistics?.total_tables || 0 }} 表格</a-tag>
            </a-space>
          </template>
        </template>
      </a-table>
      
      <!-- 文档详情抽屉 -->
      <a-drawer
        v-model:open="documentDetailVisible"
        title="文档详情"
        width="90%"
        placement="right"
      >
        <div v-if="currentDocumentDetail">
          <a-tabs v-model:activeKey="documentDetailTab">
            <a-tab-pane key="info" tab="基本信息">
              <a-descriptions :column="1" bordered style="margin-top: 16px">
                <a-descriptions-item label="文档名称">
                  {{ currentDocumentDetail.document_name }}
                </a-descriptions-item>
                <a-descriptions-item label="文档ID">
                  <code>{{ currentDocumentDetail.document_id }}</code>
                </a-descriptions-item>
                <a-descriptions-item label="创建时间">
                  {{ currentDocumentDetail.created_at }}
                </a-descriptions-item>
                <a-descriptions-item label="总Episode数">
                  {{ currentDocumentDetail.total_episodes }}
                </a-descriptions-item>
                <a-descriptions-item label="章节数">
                  <a-tag color="blue">{{ currentDocumentDetail.statistics?.total_sections || 0 }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="图片数">
                  <a-tag color="green">{{ currentDocumentDetail.statistics?.total_images || 0 }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="表格数">
                  <a-tag color="orange">{{ currentDocumentDetail.statistics?.total_tables || 0 }}</a-tag>
                </a-descriptions-item>
              </a-descriptions>
            </a-tab-pane>
            
            <a-tab-pane key="original" tab="原始文档">
              <div style="margin-top: 16px">
                <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                  <div style="color: #666; font-size: 12px;">
                    <span v-if="documentContent?.original_filename">文件名: {{ documentContent.original_filename }}</span>
                  </div>
                  <a-button 
                    type="primary" 
                    size="small" 
                    @click="loadWordDocument"
                    :loading="loadingWordDocument"
                  >
                    <template #icon><FileTextOutlined /></template>
                    加载Word文档
                  </a-button>
                </div>
                <a-spin :spinning="loadingWordDocument">
                  <div 
                    v-if="wordDocumentHtml" 
                    style="background: white; padding: 24px; border: 1px solid #d9d9d9; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto;"
                    class="word-document-viewer"
                    v-html="wordDocumentHtml"
                  ></div>
                  <a-empty v-else description="点击上方按钮加载Word文档" />
                </a-spin>
              </div>
            </a-tab-pane>
            
            <a-tab-pane key="parsed" tab="解析后内容">
              <div style="margin-top: 16px">
                <a-spin :spinning="loadingContent">
                  <div v-if="documentContent" style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 250px); overflow-y: auto;">
                    <div style="margin-bottom: 8px; color: #666; font-size: 12px;">
                      <span>字符数: {{ documentContent.parsed_content?.length || 0 }}</span>
                      <span style="margin-left: 16px;">Episode数: {{ currentDocumentDetail.total_episodes }}</span>
                      <span style="margin-left: 16px; color: #999;">（从已存储的Episode读取）</span>
                    </div>
                    <div v-if="documentContent.parsed_content" v-html="formatMarkdown(documentContent.parsed_content, currentDocumentDetail?.document_id)" style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"></div>
                    <a-empty v-else description="解析后内容不可用" />
                  </div>
                  <a-empty v-else description="正在加载..." />
                </a-spin>
              </div>
            </a-tab-pane>
            
            <a-tab-pane key="realtime" tab="实时解析">
              <div style="margin-top: 16px">
                <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                  <div style="color: #666; font-size: 12px;">
                    <span v-if="realtimeParsedContent">字符数: {{ realtimeParsedContent.parsed_content?.length || 0 }}</span>
                    <span v-if="realtimeParsedContent?.statistics" style="margin-left: 16px;">
                      章节数: {{ realtimeParsedContent.statistics.total_sections }}
                    </span>
                    <span style="margin-left: 16px; color: #1890ff;">（从原始Word文档实时解析）</span>
                  </div>
                  <a-button 
                    type="primary" 
                    size="small" 
                    @click="handleRealtimeParse"
                    :loading="loadingRealtimeParse"
                  >
                    <template #icon><ReloadOutlined /></template>
                    重新解析
                  </a-button>
                </div>
                <a-spin :spinning="loadingRealtimeParse">
                  <div 
                    v-if="realtimeParsedContent" 
                    style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto;"
                  >
                    <div v-if="realtimeParsedContent.parsed_content" v-html="formatMarkdown(realtimeParsedContent.parsed_content, currentDocumentDetail?.document_id)" style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"></div>
                    <a-empty v-else description="实时解析内容不可用" />
                  </div>
                  <a-empty v-else description="点击上方按钮进行实时解析" />
                </a-spin>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
        <a-spin v-else :spinning="loadingDetail" />
      </a-drawer>
      
      <!-- 图谱可视化抽屉 -->
      <a-drawer
        v-model:open="graphDrawerVisible"
        title="文档知识图谱"
        width="90%"
        placement="right"
        :z-index="1001"
      >
        <div v-if="currentDocumentGraph" style="height: calc(100vh - 120px);">
          <GraphVisualization 
            :data="currentDocumentGraph" 
            @nodeClick="handleNodeClick"
            @edgeClick="handleEdgeClick"
          />
        </div>
        <a-spin v-else :spinning="loadingGraph" style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;" />
      </a-drawer>
      
      <!-- 节点详情抽屉 -->
      <a-drawer
        v-model:open="nodeDetailVisible"
        title="节点属性"
        placement="right"
        :width="isImageEpisode ? 600 : 400"
        @close="selectedNode = null"
      >
        <div v-if="selectedNode" style="padding: 16px 0;">
          <!-- 图片Episode特殊显示 -->
          <div v-if="isImageEpisode" style="margin-bottom: 16px;">
            <a-alert 
              message="图片Episode" 
              type="info" 
              show-icon 
              style="margin-bottom: 16px;"
            />
            <div v-if="!imageInfo" style="padding: 16px; background: #f5f5f5; border-radius: 4px; margin-bottom: 16px;">
              <a-typography-text type="warning">
                无法提取图片信息。请检查节点属性中是否包含content和group_id字段。
              </a-typography-text>
              <div style="margin-top: 8px; font-size: 12px; color: #999;">
                <div>节点名称: {{ selectedNode.properties?.name || selectedNode.name || '-' }}</div>
                <div>是否有content: {{ selectedNode.properties?.content ? '是' : '否' }}</div>
                <div>是否有group_id: {{ selectedNode.properties?.group_id ? '是' : '否' }}</div>
              </div>
            </div>
            <div v-if="imageInfo" style="text-align: center; margin-bottom: 16px;">
              <img 
                :src="imageInfo.url" 
                :alt="imageInfo.description || '图片'"
                style="max-width: 100%; max-height: 500px; border: 1px solid #ddd; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
                @error="handleImageError"
              />
              <div style="margin-top: 8px; color: #666; font-size: 12px;">
                {{ imageInfo.description || '图片' }}
              </div>
            </div>
            <a-descriptions :column="1" bordered size="small">
              <a-descriptions-item label="图片ID">{{ imageInfo?.imageId || '-' }}</a-descriptions-item>
              <a-descriptions-item label="描述">{{ imageInfo?.description || '-' }}</a-descriptions-item>
              <a-descriptions-item label="文档ID">{{ imageInfo?.documentId || '-' }}</a-descriptions-item>
              <a-descriptions-item label="图片URL" v-if="imageInfo">
                <a :href="imageInfo.url" target="_blank" style="font-size: 12px; word-break: break-all;">{{ imageInfo.url }}</a>
              </a-descriptions-item>
            </a-descriptions>
          </div>
          
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="ID">{{ selectedNode.id }}</a-descriptions-item>
            <a-descriptions-item label="名称">{{ selectedNode.properties?.name || selectedNode.name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="类型">
              <a-tag>{{ selectedNode.labels?.[0] || selectedNode.type || 'Entity' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="所有标签">
              <a-space>
                <a-tag v-for="label in (selectedNode.labels || [selectedNode.type].filter(Boolean))" :key="label">{{ label }}</a-tag>
              </a-space>
            </a-descriptions-item>
            <a-descriptions-item label="创建时间" v-if="selectedNode.properties?.created_at">
              {{ new Date(selectedNode.properties.created_at).toLocaleString('zh-CN') }}
            </a-descriptions-item>
            <a-descriptions-item label="其他属性" v-if="hasOtherNodeProperties">
              <div style="max-height: 300px; overflow-y: auto;">
                <a-descriptions :column="1" size="small" bordered>
                  <a-descriptions-item 
                    v-for="(value, key) in otherNodeProperties" 
                    :key="key"
                    :label="key"
                  >
                    <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px;">{{ formatPropertyValue(value) }}</pre>
                  </a-descriptions-item>
                </a-descriptions>
              </div>
            </a-descriptions-item>
          </a-descriptions>
        </div>
      </a-drawer>
      
      <!-- 边详情抽屉 -->
      <a-drawer
        v-model:open="edgeDetailVisible"
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
            <a-descriptions-item label="关系名称" v-if="selectedEdge.properties?.name || selectedEdge.properties?.fact">
              {{ selectedEdge.properties?.name || selectedEdge.properties?.fact || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="创建时间" v-if="selectedEdge.properties?.created_at">
              {{ new Date(selectedEdge.properties.created_at).toLocaleString('zh-CN') }}
            </a-descriptions-item>
            <a-descriptions-item label="其他属性" v-if="hasOtherEdgeProperties">
              <div style="max-height: 300px; overflow-y: auto;">
                <a-descriptions :column="1" size="small" bordered>
                  <a-descriptions-item 
                    v-for="(value, key) in otherEdgeProperties" 
                    :key="key"
                    :label="key"
                  >
                    <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px;">{{ formatPropertyValue(value) }}</pre>
                  </a-descriptions-item>
                </a-descriptions>
              </div>
            </a-descriptions-item>
          </a-descriptions>
        </div>
      </a-drawer>
      
      <!-- Episode 详情抽屉 -->
      <a-drawer
        v-model:open="episodeDrawerVisible"
        title="Episode 结构"
        width="600px"
        placement="right"
      >
        <div v-if="currentDocumentEpisodes">
          <a-descriptions :column="1" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="文档ID">
              {{ currentDocumentEpisodes.document_id }}
            </a-descriptions-item>
            <a-descriptions-item label="文档级 Episode">
              <code v-if="currentDocumentEpisodes.document_episode">
                {{ currentDocumentEpisodes.document_episode.uuid }}
              </code>
              <span v-else style="color: #999">无</span>
            </a-descriptions-item>
            <a-descriptions-item label="章节数">
              {{ currentDocumentEpisodes.section_episodes.length }}
            </a-descriptions-item>
            <a-descriptions-item label="图片数">
              {{ currentDocumentEpisodes.image_episodes.length }}
            </a-descriptions-item>
            <a-descriptions-item label="表格数">
              {{ currentDocumentEpisodes.table_episodes.length }}
            </a-descriptions-item>
          </a-descriptions>
          
          <a-divider>章节列表（共 {{ currentDocumentEpisodes.section_episodes.length }} 个）</a-divider>
          <a-list
            :data-source="currentDocumentEpisodes.section_episodes"
            size="small"
            :pagination="{
              pageSize: 20,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 个章节`
            }"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    {{ item.name }}
                  </template>
                  <template #description>
                    <code style="font-size: 12px">{{ item.uuid }}</code>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>
        <a-spin v-else :spinning="loadingEpisodes" />
      </a-drawer>
      
      <!-- 版本列表模态框 -->
      <a-modal
        v-model:open="versionsModalVisible"
        title="文档版本列表"
        width="900px"
        :footer="null"
      >
        <a-spin :spinning="versionsLoading">
          <div v-if="documentVersions.length > 0">
            <a-table
              :columns="versionColumns"
              :data-source="documentVersions"
              :pagination="false"
              row-key="version"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'action'">
                  <a-space>
                    <a-button type="link" size="small" @click="handleCompareVersions(record, null)">
                      选择对比
                    </a-button>
                  </a-space>
                </template>
                <template v-if="column.key === 'statistics'">
                  <a-space>
                    <a-tag color="blue">{{ record.statistics?.total_episodes || 0 }} Episode</a-tag>
                    <a-tag color="green">{{ record.statistics?.total_entities || 0 }} 实体</a-tag>
                    <a-tag color="orange">{{ record.statistics?.total_relationships || 0 }} 关系</a-tag>
                  </a-space>
                </template>
              </template>
            </a-table>
            <a-divider />
            <a-space style="margin-top: 16px">
              <span>选择两个版本进行对比：</span>
              <a-select
                v-model:value="selectedVersion1"
                placeholder="选择第一个版本"
                style="width: 150px"
                :options="versionOptions"
              />
              <span>vs</span>
              <a-select
                v-model:value="selectedVersion2"
                placeholder="选择第二个版本"
                style="width: 150px"
                :options="versionOptions"
              />
              <a-button 
                type="primary" 
                @click="handleCompare"
                :disabled="!selectedVersion1 || !selectedVersion2 || selectedVersion1 === selectedVersion2"
                :loading="compareLoading"
              >
                开始对比
              </a-button>
            </a-space>
          </div>
          <a-empty v-else description="暂无版本信息" />
        </a-spin>
      </a-modal>
      
      <!-- 版本对比结果模态框 -->
      <a-modal
        v-model:open="compareModalVisible"
        title="版本对比结果"
        width="1200px"
        :footer="null"
      >
        <a-spin :spinning="compareLoading">
          <div v-if="compareResult">
            <a-descriptions title="对比概览" :column="2" bordered style="margin-bottom: 24px">
              <a-descriptions-item label="基础文档ID">
                <code>{{ compareResult.base_document_id }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="相似度">
                <a-tag color="blue">{{ (compareResult.similarity_score * 100).toFixed(2) }}%</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="版本1">
                {{ compareResult.version1_info?.version || selectedVersion1 }}
              </a-descriptions-item>
              <a-descriptions-item label="版本2">
                {{ compareResult.version2_info?.version || selectedVersion2 }}
              </a-descriptions-item>
            </a-descriptions>
            
            <a-tabs>
              <a-tab-pane key="entities" tab="实体变化">
                <a-descriptions :column="1" bordered>
                  <a-descriptions-item label="新增实体">
                    <a-tag color="green">{{ compareResult.entity_changes?.added?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="删除实体">
                    <a-tag color="red">{{ compareResult.entity_changes?.removed?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="修改实体">
                    <a-tag color="orange">{{ compareResult.entity_changes?.modified?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="保持不变">
                    <a-tag color="blue">{{ compareResult.entity_changes?.unchanged?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                </a-descriptions>
                
                <a-collapse style="margin-top: 16px">
                  <a-collapse-panel v-if="compareResult.entity_changes?.added?.length > 0" key="added" header="新增实体">
                    <a-list
                      :data-source="compareResult.entity_changes.added"
                      size="small"
                    >
                      <template #renderItem="{ item }">
                        <a-list-item>
                          <a-tag color="green">{{ item.type || 'Entity' }}</a-tag>
                          <strong>{{ item.name }}</strong>
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
                          <a-tag color="red">{{ item.type || 'Entity' }}</a-tag>
                          <strong>{{ item.name }}</strong>
                        </a-list-item>
                      </template>
                    </a-list>
                  </a-collapse-panel>
                  <a-collapse-panel v-if="compareResult.entity_changes?.modified?.length > 0" key="modified" header="修改实体">
                    <a-list
                      :data-source="compareResult.entity_changes.modified"
                      size="small"
                    >
                      <template #renderItem="{ item }">
                        <a-list-item>
                          <a-tag color="orange">{{ item.type || 'Entity' }}</a-tag>
                          <strong>{{ item.name }}</strong>
                          <div style="color: #666; font-size: 12px; margin-top: 4px">
                            变化: {{ JSON.stringify(item.changes) }}
                          </div>
                        </a-list-item>
                      </template>
                    </a-list>
                  </a-collapse-panel>
                </a-collapse>
              </a-tab-pane>
              
              <a-tab-pane key="relationships" tab="关系变化">
                <a-descriptions :column="1" bordered>
                  <a-descriptions-item label="新增关系">
                    <a-tag color="green">{{ compareResult.relationship_changes?.added?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="删除关系">
                    <a-tag color="red">{{ compareResult.relationship_changes?.removed?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="修改关系">
                    <a-tag color="orange">{{ compareResult.relationship_changes?.modified?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                  <a-descriptions-item label="保持不变">
                    <a-tag color="blue">{{ compareResult.relationship_changes?.unchanged?.length || 0 }} 个</a-tag>
                  </a-descriptions-item>
                </a-descriptions>
                
                <a-collapse style="margin-top: 16px">
                  <a-collapse-panel v-if="compareResult.relationship_changes?.added?.length > 0" key="added" header="新增关系">
                    <a-list
                      :data-source="compareResult.relationship_changes.added"
                      size="small"
                    >
                      <template #renderItem="{ item }">
                        <a-list-item>
                          <a-tag color="green">{{ item.type || 'RELATES_TO' }}</a-tag>
                          <strong>{{ item.source }}</strong> → <strong>{{ item.target }}</strong>
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
                          <a-tag color="red">{{ item.type || 'RELATES_TO' }}</a-tag>
                          <strong>{{ item.source }}</strong> → <strong>{{ item.target }}</strong>
                        </a-list-item>
                      </template>
                    </a-list>
                  </a-collapse-panel>
                </a-collapse>
              </a-tab-pane>
            </a-tabs>
          </div>
          <a-empty v-else description="暂无对比结果" />
        </a-spin>
      </a-modal>
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { FileTextOutlined, ReloadOutlined, EyeOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { getDocumentEpisodes, getDocumentList, getDocumentGraph, getDocumentContent, getDocumentDownloadUrl, getRealtimeParsedContent, getDocumentVersions, compareDocumentVersions, deleteDocument } from '../api/wordDocument'
import GraphVisualization from './GraphVisualization.vue'
import mammoth from 'mammoth'

const documents = ref([])
const loading = ref(false)
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

const episodeDrawerVisible = ref(false)
const currentDocumentEpisodes = ref(null)
const loadingEpisodes = ref(false)

const documentDetailVisible = ref(false)
const currentDocumentDetail = ref(null)
const loadingDetail = ref(false)
const documentDetailTab = ref('info')
const documentContent = ref(null)
const loadingContent = ref(false)
const wordDocumentHtml = ref(null)
const loadingWordDocument = ref(false)
const realtimeParsedContent = ref(null)
const loadingRealtimeParse = ref(false)

const graphDrawerVisible = ref(false)
const currentDocumentGraph = ref(null)
const loadingGraph = ref(false)

// 节点和边详情
const selectedNode = ref(null)
const selectedEdge = ref(null)
const nodeDetailVisible = ref(false)
const edgeDetailVisible = ref(false)

// 版本管理
const versionsModalVisible = ref(false)
const versionsLoading = ref(false)
const currentBaseDocumentId = ref(null)
const documentVersions = ref([])

// 版本对比
const compareModalVisible = ref(false)
const compareLoading = ref(false)
const compareResult = ref(null)
const selectedVersion1 = ref(null)
const selectedVersion2 = ref(null)

const columns = [
  {
    title: '文档名称',
    dataIndex: 'document_name',
    key: 'document_name'
  },
  {
    title: '版本',
    key: 'version',
    width: 80
  },
  {
    title: '文档ID',
    dataIndex: 'document_id',
    key: 'document_id'
  },
  {
    title: '统计信息',
    key: 'statistics',
    width: 200
  },
  {
    title: '操作',
    key: 'action',
    width: 200
  }
]

onMounted(() => {
  loadDocuments()
})

const loadDocuments = async () => {
  loading.value = true
  try {
    const response = await getDocumentList('qianwen', pagination.value.pageSize, (pagination.value.current - 1) * pagination.value.pageSize)
    // 注意：api/index.js 的响应拦截器已经返回了 response.data，所以这里直接使用 response
    if (response && typeof response === 'object') {
      documents.value = response.documents || []
      pagination.value.total = response.total || 0
    } else {
      console.error('API响应格式异常:', response)
      message.error('加载文档列表失败: API响应格式异常')
    }
  } catch (error) {
    console.error('加载文档列表错误:', error)
    const errorMessage = error?.message || error?.response?.data?.detail || '网络错误，请检查后端服务是否正常运行'
    message.error(`加载文档列表失败: ${errorMessage}`)
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadDocuments()
}

const handleView = async (record) => {
  documentDetailVisible.value = true
  loadingDetail.value = true
  loadingContent.value = true
  currentDocumentDetail.value = null
  documentContent.value = null
  documentDetailTab.value = 'info'
  
  // 直接使用record数据，因为已经包含了所有详情信息
  currentDocumentDetail.value = record
  loadingDetail.value = false
  
  // 加载文档内容
  try {
    const response = await getDocumentContent(record.document_id, 'qianwen')
    documentContent.value = response
  } catch (error) {
    message.error(`获取文档内容失败: ${error.message || '未知错误'}`)
  } finally {
    loadingContent.value = false
  }
}

// 简单的Markdown格式化函数（用于显示解析后的内容）
const formatMarkdown = (text, documentId = null) => {
  if (!text) return ''
  
  // 处理图片链接（将相对路径转换为完整URL）
  if (documentId) {
    // 匹配Markdown图片语法: ![alt](url)
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
      // 如果URL是相对路径，转换为完整API路径
      if (url.startsWith('/api/word-document/')) {
        return match // 已经是完整路径
      } else if (url.includes('images/')) {
        // 提取image_id
        const imageId = url.split('images/')[1] || url
        const fullUrl = `/api/word-document/${documentId}/images/${imageId}`
        return `![${alt}](${fullUrl})`
      }
      return match
    })
    
    // 处理图片链接（纯链接格式）
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      // 检查是否是OLE对象的链接
      if (url.includes('/ole/') && url.startsWith('/api/word-document/')) {
        // 提取oleId（去除查询参数）
        let oleId = url.split('/ole/')[1] || ''
        oleId = oleId.split('?')[0].split('#')[0].split('/')[0]
        
        if (!oleId) return match
        
        // 构建预览和下载URL（使用干净的URL，避免重复查询参数）
        const baseUrl = `/api/word-document/${documentId}/ole/${oleId}`
        const previewUrl = `${baseUrl}?view=preview`
        const downloadUrl = `${baseUrl}?view=download`
        
        // 生成唯一的ID用于模态框
        const modalId = `ole-viewer-${documentId}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
        
        // 如果链接文本是"查看"，使用预览模式（弹窗）；如果是"下载"，直接下载
        if (linkText === '查看' || linkText === '预览') {
          return `<a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        } else if (linkText === '下载') {
          // 直接下载，不使用弹窗 - 使用JavaScript触发下载
          return `<a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        } else {
          // 默认使用预览模式
          return `<a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        }
      }
      
      // 处理其他链接
      if (url.startsWith('/api/word-document/')) {
        // 如果是图片链接
        if (url.includes('images/')) {
          const imageId = url.split('images/')[1]?.split('?')[0] || url
          const fullUrl = `/api/word-document/${documentId}/images/${imageId}`
          return `<a href="${fullUrl}" target="_blank">${linkText}</a>`
        }
        // 其他API链接
        return `<a href="${url}" target="_blank">${linkText}</a>`
      }
      
      return match
    })
  }
  
  // 将Markdown格式转换为HTML（简化版）
  // 先处理图片，转换为可点击链接（在转换为HTML之前）
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    // 如果URL是图片API路径，转换为可点击链接
    if (url.includes('/images/') || url.startsWith('/api/word-document/')) {
      // 提取图片ID或使用alt文本
      const linkText = alt || url.split('/images/')[1] || url.split('/').pop() || '图片'
      return `[${linkText}](${url})`
    }
    return match
  })
  
  return text
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // 处理链接（包括转换后的图片链接）
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      // 如果是图片链接，显示为可点击链接
      if (url.includes('/images/') || url.startsWith('/api/word-document/') && url.includes('images/')) {
        return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
      }
      return `<a href="${url}" target="_blank">${linkText}</a>`
    })
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

// 打开嵌入文档查看器
const openOleViewer = (previewUrl, downloadUrl, modalId) => {
  // 检查是否已存在模态框，如果存在则先移除
  const existingModal = document.getElementById(modalId)
  if (existingModal) {
    document.body.removeChild(existingModal)
  }
  
  // 创建模态框
  const modal = document.createElement('div')
  modal.id = modalId
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
  `
  
  const content = document.createElement('div')
  content.style.cssText = `
    background: white;
    border-radius: 8px;
    width: 90%;
    height: 90%;
    max-width: 1200px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  `
  
  const header = document.createElement('div')
  header.style.cssText = `
    padding: 16px;
    border-bottom: 1px solid #e8e8e8;
    display: flex;
    justify-content: space-between;
    align-items: center;
  `
  
  const title = document.createElement('span')
  title.textContent = '嵌入文档查看器'
  title.style.cssText = 'font-size: 16px; font-weight: bold;'
  
  const buttonGroup = document.createElement('div')
  buttonGroup.style.cssText = 'display: flex; gap: 8px;'
  
  const downloadBtn = document.createElement('button')
  downloadBtn.textContent = '下载'
  downloadBtn.style.cssText = `
    background: #1890ff;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  `
  downloadBtn.onclick = () => {
    window.open(downloadUrl, '_blank')
  }
  
  const closeBtn = document.createElement('button')
  closeBtn.textContent = '×'
  closeBtn.style.cssText = `
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
    padding: 0;
    width: 30px;
    height: 30px;
    line-height: 30px;
  `
  closeBtn.onclick = () => {
    document.body.removeChild(modal)
  }
  
  buttonGroup.appendChild(downloadBtn)
  buttonGroup.appendChild(closeBtn)
  header.appendChild(title)
  header.appendChild(buttonGroup)
  
  const body = document.createElement('div')
  body.style.cssText = `
    flex: 1;
    overflow: auto;
    padding: 0;
  `
  
  // 使用iframe显示预览内容（后端会返回HTML格式的Excel预览）
  const iframe = document.createElement('iframe')
  iframe.style.cssText = 'width: 100%; height: 100%; border: none;'
  iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-popups allow-forms')
  
  // 添加加载状态
  const loadingDiv = document.createElement('div')
  loadingDiv.style.cssText = 'text-align: center; padding: 40px; color: #666;'
  loadingDiv.innerHTML = '<p>正在加载预览...</p>'
  body.appendChild(loadingDiv)
  
  // 先添加iframe到DOM，然后设置src
  body.appendChild(iframe)
  
  // 监听iframe加载完成
  iframe.onload = () => {
    // 移除加载提示
    if (body.contains(loadingDiv)) {
      body.removeChild(loadingDiv)
    }
  }
  
  // 如果加载失败，显示错误信息
  iframe.onerror = () => {
    if (body.contains(loadingDiv)) {
      body.removeChild(loadingDiv)
    }
    body.innerHTML = `
      <div style="text-align: center; padding: 40px;">
        <p style="color: #ff4d4f; margin-bottom: 16px;">预览加载失败</p>
        <p style="color: #666; margin-bottom: 16px;">请尝试下载文件后查看。</p>
        <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; text-decoration: underline; display: inline-block; padding: 8px 16px; background: #f0f0f0; border-radius: 4px; cursor: pointer;">下载文件</a>
      </div>
    `
  }
  
  // 设置超时处理（10秒）
  const timeoutId = setTimeout(() => {
    if (body.contains(loadingDiv)) {
      // 如果10秒后还在加载，显示错误信息
      body.removeChild(loadingDiv)
      body.innerHTML = `
        <div style="text-align: center; padding: 40px;">
          <p style="color: #ff4d4f; margin-bottom: 16px;">预览加载超时</p>
          <p style="color: #666; margin-bottom: 16px;">请尝试下载文件后查看。</p>
          <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; text-decoration: underline; display: inline-block; padding: 8px 16px; background: #f0f0f0; border-radius: 4px; cursor: pointer;">下载文件</a>
        </div>
      `
    }
  }, 10000)
  
  // 设置iframe的src（延迟设置，确保DOM已准备好）
  setTimeout(() => {
    iframe.src = previewUrl
    // 如果iframe加载成功，清除超时
    iframe.onload = () => {
      clearTimeout(timeoutId)
      if (body.contains(loadingDiv)) {
        body.removeChild(loadingDiv)
      }
    }
  }, 100)
  
  content.appendChild(header)
  content.appendChild(body)
  modal.appendChild(content)
  
  // 点击背景关闭
  modal.onclick = (e) => {
    if (e.target === modal) {
      document.body.removeChild(modal)
    }
  }
  
  document.body.appendChild(modal)
}

// 直接下载OLE文件（不使用弹窗）
const downloadOleFile = (downloadUrl) => {
  // 创建一个临时的a标签来触发下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.target = '_blank'
  link.download = '' // 让浏览器自动处理文件名
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 将函数挂载到window对象，以便在HTML中调用
if (typeof window !== 'undefined') {
  window.openOleViewer = openOleViewer
  window.downloadOleFile = downloadOleFile
}

// 加载Word文档并转换为HTML（使用后端API，包含嵌入文件链接）
const loadWordDocument = async () => {
  if (!currentDocumentDetail.value?.document_id) {
    message.warning('文档ID不存在')
    return
  }
  
  loadingWordDocument.value = true
  wordDocumentHtml.value = null
  
  try {
    // 使用后端API预览Word文档（包含嵌入文件链接）
    const previewUrl = `/api/word-document/${currentDocumentDetail.value.document_id}/preview?provider=qianwen`
    console.log('加载Word文档，URL:', previewUrl)
    
    const response = await fetch(previewUrl)
    if (!response.ok) {
      const errorText = await response.text()
      console.error('API响应错误:', response.status, errorText)
      throw new Error(`加载失败: ${response.statusText}`)
    }
    
    // 获取HTML内容
    const html = await response.text()
    console.log('获取到HTML内容长度:', html.length)
    console.log('HTML内容预览:', html.substring(0, 500))
    
    // 如果返回的是完整的HTML文档，提取body内容
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const bodyContent = doc.body ? doc.body.innerHTML : html
    wordDocumentHtml.value = bodyContent || html
    console.log('设置wordDocumentHtml，长度:', wordDocumentHtml.value.length)
    console.log('wordDocumentHtml预览:', wordDocumentHtml.value.substring(0, 500))
    
    // 处理嵌入文件的链接（确保点击时使用正确的处理函数）
    setTimeout(() => {
      const viewer = document.querySelector('.word-document-viewer')
      if (viewer) {
        // 处理OLE对象的链接
        const oleLinks = viewer.querySelectorAll('a[href*="/ole/"]')
        oleLinks.forEach(link => {
          const href = link.getAttribute('href')
          if (href) {
            // 清理URL，移除重复的查询参数
            const cleanHref = href.split('?')[0]
            const isPreview = href.includes('view=preview')
            const isDownload = href.includes('view=download') || link.textContent === '下载'
            
            if (isPreview || link.textContent === '查看' || link.textContent === '预览') {
              const previewUrl = `${cleanHref}?view=preview`
              const downloadUrl = `${cleanHref}?view=download`
              const oleId = cleanHref.match(/\/ole\/([^?]+)/)?.[1]
              const modalId = `ole-viewer-${currentDocumentDetail.value.document_id}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
              
              link.onclick = (e) => {
                e.preventDefault()
                if (window.openOleViewer) {
                  window.openOleViewer(previewUrl, downloadUrl, modalId)
                } else {
                  window.open(previewUrl, '_blank')
                }
                return false
              }
            } else if (isDownload || link.textContent === '下载') {
              const downloadUrl = `${cleanHref}?view=download`
              link.onclick = (e) => {
                e.preventDefault()
                if (window.downloadOleFile) {
                  window.downloadOleFile(downloadUrl)
                } else {
                  // 创建一个临时a元素来触发下载
                  const a = document.createElement('a')
                  a.href = downloadUrl
                  a.download = ''
                  document.body.appendChild(a)
                  a.click()
                  document.body.removeChild(a)
                }
                return false
              }
            }
          }
        })
      }
    }, 100)
    
    message.success('Word文档加载成功')
  } catch (error) {
    console.error('加载Word文档失败:', error)
    message.error(`加载Word文档失败: ${error.message || '未知错误'}`)
  } finally {
    loadingWordDocument.value = false
  }
}

// 实时解析Word文档
const handleRealtimeParse = async () => {
  if (!currentDocumentDetail.value?.document_id) {
    message.warning('文档ID不存在')
    return
  }
  
  loadingRealtimeParse.value = true
  realtimeParsedContent.value = null
  
  try {
    const response = await getRealtimeParsedContent(currentDocumentDetail.value.document_id, 'qianwen', 8000)
    realtimeParsedContent.value = response
    
    message.success(`实时解析成功：${response.statistics?.total_sections || 0} 个章节，${response.parsed_content?.length || 0} 字符`)
  } catch (error) {
    console.error('实时解析失败:', error)
    message.error(`实时解析失败: ${error.message || '未知错误'}`)
  } finally {
    loadingRealtimeParse.value = false
  }
}

const handleViewEpisodes = async (record) => {
  episodeDrawerVisible.value = true
  loadingEpisodes.value = true
  currentDocumentEpisodes.value = null
  
  try {
    const response = await getDocumentEpisodes(record.document_id, false, 'qianwen')
    // 注意：api/index.js 的响应拦截器已经返回了 response.data，所以这里直接使用 response
    currentDocumentEpisodes.value = response
  } catch (error) {
    message.error(`获取 Episode 信息失败: ${error.message || '未知错误'}`)
  } finally {
    loadingEpisodes.value = false
  }
}

const handleViewGraph = async (record) => {
  graphDrawerVisible.value = true
  loadingGraph.value = true
  currentDocumentGraph.value = null
  
  try {
    const response = await getDocumentGraph(record.document_id, 'qianwen', 500)
    // 注意：api/index.js 的响应拦截器已经返回了 response.data，所以这里直接使用 response
    // GraphVisualization组件期望的格式：{ nodes: [], edges: [] }
    // 需要将后端返回的节点格式转换为GraphVisualization期望的格式
    const nodes = (response.nodes || []).map(node => ({
      id: String(node.id),
      labels: node.labels || [],
      name: node.name || node.properties?.name || '',
      type: node.type || (node.labels && node.labels[0]) || 'Entity',
      properties: node.properties || {}
    }))
    
    const edges = (response.edges || []).map(edge => ({
      id: String(edge.id),
      source: String(edge.source),
      target: String(edge.target),
      type: edge.type || 'RELATES_TO',
      properties: edge.properties || {}
    }))
    
    currentDocumentGraph.value = {
      nodes: nodes,
      edges: edges
    }
  } catch (error) {
    message.error(`获取图谱数据失败: ${error.message || '未知错误'}`)
  } finally {
    loadingGraph.value = false
  }
}

const handleNodeClick = (node) => {
  selectedNode.value = node
  nodeDetailVisible.value = true
}

const handleViewVersions = async (record) => {
  versionsModalVisible.value = true
  versionsLoading.value = true
  currentBaseDocumentId.value = record.document_id
  documentVersions.value = []
  selectedVersion1.value = null
  selectedVersion2.value = null
  
  try {
    const response = await getDocumentVersions(record.document_id, 'qianwen')
    documentVersions.value = response.versions || []
    message.success(`找到 ${documentVersions.value.length} 个版本`)
  } catch (error) {
    message.error(`获取版本列表失败: ${error.message || '未知错误'}`)
  } finally {
    versionsLoading.value = false
  }
}

const versionColumns = [
  { title: '版本', dataIndex: 'version', key: 'version', width: 100 },
  { title: '版本号', dataIndex: 'version_number', key: 'version_number', width: 100 },
  { title: '文档名称', dataIndex: 'document_name', key: 'document_name' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '统计信息', key: 'statistics', width: 250 },
  { title: '操作', key: 'action', width: 120 }
]

const versionOptions = computed(() => {
  return documentVersions.value.map(v => ({
    label: `${v.version} (${v.version_number})`,
    value: v.version
  }))
})

const handleCompareVersions = (version1, version2) => {
  selectedVersion1.value = version1.version
  if (version2) {
    selectedVersion2.value = version2.version
  }
}

const handleCompare = async () => {
  if (!selectedVersion1.value || !selectedVersion2.value || selectedVersion1.value === selectedVersion2.value) {
    message.warning('请选择两个不同的版本进行对比')
    return
  }
  
  compareModalVisible.value = true
  compareLoading.value = true
  compareResult.value = null
  
  try {
    const response = await compareDocumentVersions(
      currentBaseDocumentId.value,
      selectedVersion1.value,
      selectedVersion2.value,
      'qianwen'
    )
    compareResult.value = response
    message.success('版本对比完成')
  } catch (error) {
    message.error(`版本对比失败: ${error.message || '未知错误'}`)
  } finally {
    compareLoading.value = false
  }
}

const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文档 "${record.document_name}" 吗？\n\n此操作将删除：\n- 所有版本的Episode\n- 所有相关的实体\n- 所有相关的关系\n\n此操作不可恢复！`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteDocument(record.document_id, 'qianwen')
        message.success(response.message || '文档删除成功')
        // 重新加载文档列表
        loadDocuments()
      } catch (error) {
        message.error(`删除文档失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

const handleEdgeClick = (edge) => {
  selectedEdge.value = edge
  edgeDetailVisible.value = true
}

// 判断是否是图片Episode
const isImageEpisode = computed(() => {
  if (!selectedNode.value) {
    console.log('[图片Episode检测] 节点为空')
    return false
  }
  const labels = selectedNode.value.labels || []
  const name = selectedNode.value.properties?.name || selectedNode.value.name || ''
  const isEpisodic = labels.includes('Episodic')
  const hasImage = name.includes('图片')
  const result = isEpisodic && hasImage
  console.log('[图片Episode检测]', { 
    labels, 
    name, 
    isEpisodic, 
    hasImage, 
    result,
    properties: selectedNode.value.properties 
  })
  return result
})

// 从图片Episode中提取图片信息（最简单直接的方法）
const imageInfo = computed(() => {
  if (!isImageEpisode.value || !selectedNode.value) {
    console.log('[图片信息提取] 跳过，isImageEpisode:', isImageEpisode.value, 'selectedNode:', !!selectedNode.value)
    return null
  }
  
  const props = selectedNode.value.properties || {}
  const name = props.name || selectedNode.value.name || ''
  const groupId = props.group_id || ''
  
  console.log('[图片信息提取] 开始提取', { name, groupId, propsKeys: Object.keys(props) })
  
  // 方法1: 从名称中直接提取图片编号（最简单可靠）
  // 格式：..._图片_3_图片 3 或 ..._图片_3_...
  const nameMatch = name.match(/图片_(\d+)/)
  if (!nameMatch) {
    console.log('[图片信息提取] 无法从名称中提取图片编号:', name)
    return null
  }
  
  const imageNumber = nameMatch[1]
  const imageId = `image_${imageNumber}`
  
  // 提取描述（从名称中，格式：..._图片_3_描述）
  let description = ''
  const descMatch = name.match(/图片_\d+_(.+)/)
  if (descMatch) {
    description = descMatch[1].trim()
  } else {
    description = `图片 ${imageNumber}`
  }
  
  if (!groupId) {
    console.log('[图片信息提取] 缺少group_id')
    return null
  }
  
  // 构建图片URL
  const imageUrl = `/api/word-document/${groupId}/images/${imageId}?provider=qianwen`
  
  const result = {
    imageId,
    description,
    documentId: groupId,
    url: imageUrl
  }
  
  console.log('[图片信息提取] 成功提取', result)
  return result
})

const handleImageError = (event) => {
  console.error('图片加载失败:', event.target.src)
  message.error('图片加载失败，请检查图片是否存在')
}

const hasOtherNodeProperties = computed(() => {
  if (!selectedNode.value?.properties) return false
  const excludeKeys = ['name', 'created_at', 'name_embedding', 'name_emb', 'content', 'group_id']
  return Object.keys(selectedNode.value.properties).some(key => !excludeKeys.includes(key))
})

const otherNodeProperties = computed(() => {
  if (!selectedNode.value?.properties) return {}
  const excludeKeys = ['name', 'created_at', 'name_embedding', 'name_emb', 'content', 'group_id']
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
</script>

<style scoped>
.document-management {
  max-width: 1200px;
}

.word-document-viewer {
  font-family: 'Microsoft YaHei', 'SimSun', 'Times New Roman', serif;
  line-height: 1.6;
  color: #333;
}

.word-document-viewer :deep(p) {
  margin: 8px 0;
}

.word-document-viewer :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  border: 1px solid #ddd;
}

.word-document-viewer :deep(table td),
.word-document-viewer :deep(table th) {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

.word-document-viewer :deep(table th) {
  background-color: #f5f5f5;
  font-weight: bold;
}

.word-document-viewer :deep(h1) {
  font-size: 24px;
  font-weight: bold;
  margin: 16px 0;
}

.word-document-viewer :deep(h2) {
  font-size: 20px;
  font-weight: bold;
  margin: 14px 0;
}

.word-document-viewer :deep(h3) {
  font-size: 16px;
  font-weight: bold;
  margin: 12px 0;
}

.word-document-viewer :deep(strong) {
  font-weight: bold;
}

.word-document-viewer :deep(em) {
  font-style: italic;
}

.word-document-viewer :deep(ul),
.word-document-viewer :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}
</style>

