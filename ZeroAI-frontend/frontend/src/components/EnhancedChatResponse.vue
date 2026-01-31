<template>
  <div class="enhanced-chat-response">
    <!-- 直接回答 -->
    <a-collapse v-model:activeKey="activeKeys" :bordered="false" expand-icon-position="end">
      <!-- 直接回答面板 -->
      <a-collapse-panel key="answer" header="💬 直接回答" class="answer-panel">
        <div 
          v-html="formattedAnswer"
          class="answer-content"
        ></div>
        
        <!-- 知识覆盖度 -->
        <div v-if="knowledgeCoverage" class="knowledge-coverage">
          <a-tag :color="coverageColor">
            📊 知识覆盖度: {{ knowledgeCoverage.score }}%
          </a-tag>
          <span class="coverage-desc">{{ knowledgeCoverage.description }}</span>
        </div>
        
        <!-- 知识缺口提示 -->
        <a-alert
          v-if="knowledgeGap"
          type="info"
          show-icon
          class="knowledge-gap"
        >
          <template #icon><BulbOutlined /></template>
          <template #message>
            <span>知识缺口提示</span>
          </template>
          <template #description>
            {{ knowledgeGap.message }}
            <a-button 
              v-if="knowledgeGap.suggestions && knowledgeGap.suggestions.length > 0"
              type="link" 
              size="small"
              @click="showGapSuggestions = !showGapSuggestions"
            >
              {{ showGapSuggestions ? '收起建议' : '查看建议' }}
            </a-button>
            <ul v-if="showGapSuggestions && knowledgeGap.suggestions" style="margin: 8px 0 0 0; padding-left: 16px">
              <li v-for="(s, i) in knowledgeGap.suggestions" :key="i">{{ s }}</li>
            </ul>
          </template>
        </a-alert>
      </a-collapse-panel>
      
      <!-- 相关文档总结面板 -->
      <a-collapse-panel 
        v-if="documentSummaries && documentSummaries.length > 0" 
        key="documents" 
        class="documents-panel"
      >
        <template #header>
          <a-space>
            <span>📚 相关文档总结</span>
            <a-tag color="blue" size="small">{{ documentSummaries.length }} 个文档</a-tag>
          </a-space>
        </template>
        
        <div class="document-summaries">
          <div 
            v-for="(doc, index) in documentSummaries" 
            :key="doc.document_id || index"
            class="document-summary-item"
          >
            <div class="doc-header">
              <a-space>
                <FileWordOutlined style="color: #2b5797" />
                <span class="doc-name">{{ doc.document_name }}</span>
                <a-tag v-if="doc.knowledge_base_name" size="small">
                  {{ doc.knowledge_base_name }}
                </a-tag>
              </a-space>
              <a-tag :color="getRelationshipColor(doc.relationship)" size="small">
                {{ doc.relationship }}
              </a-tag>
            </div>
            
            <div class="doc-content">
              <div class="doc-key-content" v-if="doc.key_content">
                <strong>相关内容：</strong>{{ doc.key_content }}
              </div>
              <div class="doc-suggestion" v-if="doc.suggestion">
                <BulbOutlined style="color: #faad14" />
                <span>{{ doc.suggestion }}</span>
              </div>
            </div>
            
            <div class="doc-footer">
              <a-button 
                type="link" 
                size="small" 
                @click="$emit('view-document', doc)"
              >
                <template #icon><EyeOutlined /></template>
                查看文档
              </a-button>
              <a-rate 
                :value="doc.relevance_score / 20" 
                disabled 
                allow-half 
                style="font-size: 12px"
              />
            </div>
          </div>
        </div>
      </a-collapse-panel>
      
      <!-- 参考来源面板 -->
      <a-collapse-panel 
        v-if="references && references.length > 0" 
        key="references"
        class="references-panel"
      >
        <template #header>
          <a-space>
            <span>📎 参考来源</span>
            <a-tag color="green" size="small">{{ references.length }} 条</a-tag>
          </a-space>
        </template>
        
        <div class="references-list">
          <div 
            v-for="(ref, index) in references" 
            :key="index"
            class="reference-item"
          >
            <span class="ref-index">[{{ index + 1 }}]</span>
            <span class="ref-content">{{ ref.content }}</span>
            <a-button 
              type="link" 
              size="small"
              @click="$emit('view-reference', ref)"
            >
              <template #icon><LinkOutlined /></template>
            </a-button>
          </div>
        </div>
      </a-collapse-panel>
      
      <!-- 知识图谱详情面板（可选） -->
      <a-collapse-panel 
        v-if="graphDetails && (graphDetails.entities?.length || graphDetails.edges?.length)" 
        key="graph"
        class="graph-panel"
      >
        <template #header>
          <a-space>
            <span>🔗 知识图谱详情</span>
            <a-tag v-if="graphDetails.entities" size="small">
              {{ graphDetails.entities.length }} 实体
            </a-tag>
            <a-tag v-if="graphDetails.edges" size="small">
              {{ graphDetails.edges.length }} 关系
            </a-tag>
          </a-space>
        </template>
        
        <!-- 实体列表 -->
        <div v-if="graphDetails.entities?.length" style="margin-bottom: 12px">
          <div style="font-weight: 500; margin-bottom: 8px">实体：</div>
          <a-space wrap>
            <a-tag 
              v-for="entity in graphDetails.entities.slice(0, 10)" 
              :key="entity.uuid"
              :color="getEntityColor(entity.type)"
            >
              {{ entity.name }}
            </a-tag>
            <span v-if="graphDetails.entities.length > 10" style="color: #999">
              等 {{ graphDetails.entities.length }} 个
            </span>
          </a-space>
        </div>
        
        <!-- 关系列表 -->
        <div v-if="graphDetails.edges?.length">
          <div style="font-weight: 500; margin-bottom: 8px">关系：</div>
          <div 
            v-for="edge in graphDetails.edges.slice(0, 5)" 
            :key="edge.uuid"
            class="edge-item"
          >
            <span class="edge-source">{{ edge.source_name }}</span>
            <ArrowRightOutlined style="margin: 0 8px; color: #999" />
            <a-tag color="blue" size="small">{{ edge.name }}</a-tag>
            <ArrowRightOutlined style="margin: 0 8px; color: #999" />
            <span class="edge-target">{{ edge.target_name }}</span>
          </div>
          <div v-if="graphDetails.edges.length > 5" style="color: #999; font-size: 12px; margin-top: 4px">
            还有 {{ graphDetails.edges.length - 5 }} 个关系...
          </div>
        </div>
      </a-collapse-panel>
    </a-collapse>
    
    <!-- 追问引导 -->
    <div v-if="followupQuestions && followupQuestions.length > 0" class="followup-questions">
      <div class="followup-header">💡 您可能还想问：</div>
      <a-space wrap>
        <a-button 
          v-for="(q, index) in followupQuestions" 
          :key="index"
          size="small"
          @click="$emit('followup', q)"
        >
          {{ q }}
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  BulbOutlined,
  FileWordOutlined,
  EyeOutlined,
  LinkOutlined,
  ArrowRightOutlined
} from '@ant-design/icons-vue'

const props = defineProps({
  answer: {
    type: String,
    default: ''
  },
  documentSummaries: {
    type: Array,
    default: () => []
  },
  knowledgeCoverage: {
    type: Object,
    default: null
  },
  knowledgeGap: {
    type: Object,
    default: null
  },
  references: {
    type: Array,
    default: () => []
  },
  graphDetails: {
    type: Object,
    default: null
  },
  followupQuestions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['view-document', 'view-reference', 'followup'])

// 默认展开直接回答和相关文档总结
const activeKeys = ref(['answer', 'documents'])
const showGapSuggestions = ref(false)

// 格式化回答（简单Markdown转HTML）
const formattedAnswer = computed(() => {
  if (!props.answer) return ''
  let text = props.answer
  
  // 处理参考标注 [1], [2] 等
  text = text.replace(/\[(\d+)\]/g, '<sup class="ref-mark">[$1]</sup>')
  
  // 处理粗体
  text = text.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  
  // 处理换行
  text = text.replace(/\n/g, '<br>')
  
  return text
})

// 知识覆盖度颜色
const coverageColor = computed(() => {
  if (!props.knowledgeCoverage) return 'default'
  const score = props.knowledgeCoverage.score
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
})

// 辅助方法
const getRelationshipColor = (relationship) => {
  if (relationship === '核心来源') return 'green'
  if (relationship === '补充来源') return 'blue'
  return 'default'
}

const getEntityColor = (type) => {
  const colors = {
    'Requirement': 'green',
    'Feature': 'blue',
    'Module': 'cyan',
    'Person': 'purple',
    'Organization': 'orange'
  }
  return colors[type] || 'default'
}
</script>

<style scoped>
.enhanced-chat-response {
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  overflow: hidden;
}

.answer-panel :deep(.ant-collapse-header) {
  background: #f6ffed;
}

.documents-panel :deep(.ant-collapse-header) {
  background: #e6f7ff;
}

.references-panel :deep(.ant-collapse-header) {
  background: #f6ffed;
}

.graph-panel :deep(.ant-collapse-header) {
  background: #f9f0ff;
}

.answer-content {
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.answer-content :deep(.ref-mark) {
  color: #1890ff;
  cursor: pointer;
}

.knowledge-coverage {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.coverage-desc {
  font-size: 12px;
  color: #666;
}

.knowledge-gap {
  margin-top: 12px;
}

.document-summaries {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.document-summary-item {
  background: #fafafa;
  border-radius: 8px;
  padding: 12px;
}

.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.doc-name {
  font-weight: 500;
}

.doc-content {
  font-size: 13px;
  color: #666;
}

.doc-key-content {
  margin-bottom: 4px;
}

.doc-suggestion {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #faad14;
  font-size: 12px;
}

.doc-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.references-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reference-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.ref-index {
  color: #1890ff;
  font-weight: 500;
}

.ref-content {
  flex: 1;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edge-item {
  display: flex;
  align-items: center;
  font-size: 13px;
  margin-bottom: 4px;
}

.edge-source, .edge-target {
  color: #333;
}

.followup-questions {
  padding: 12px 16px;
  background: #fafafa;
  border-top: 1px solid #e8e8e8;
}

.followup-header {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}
</style>

