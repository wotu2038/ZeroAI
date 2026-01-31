<template>
  <div>
    <!-- 配置区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item label="用户需求">
        <a-textarea
          v-model:value="userQuery"
          :rows="4"
          placeholder="描述你的需求或问题..."
          :disabled="executing"
        />
      </a-form-item>

      <a-form-item label="Mem0注入结果">
        <a-textarea
          v-model:value="injectedResultsJson"
          :rows="6"
          placeholder="请粘贴Mem0注入结果（JSON格式），或从Tab 6复制结果"
          :disabled="executing"
        />
        <div style="margin-top: 8px">
          <a-button size="small" @click="loadFromTab6" :disabled="executing">
            从Tab 6加载结果
          </a-button>
        </div>
      </a-form-item>

      <a-form-item label="LLM配置">
        <a-radio-group v-model:value="provider" :disabled="executing">
          <a-radio value="deepseek">DeepSeek</a-radio>
          <a-radio value="qwen">Qwen</a-radio>
          <a-radio value="kimi">Kimi</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="检索配置">
        <a-space>
          <a-radio-group v-model:value="retrievalScope">
            <a-radio value="all">全部文档</a-radio>
            <a-radio value="specified">指定文档</a-radio>
          </a-radio-group>
          <a-input-number
            v-model:value="topK"
            :min="10"
            :max="100"
            :step="10"
            style="width: 100px; margin-left: 24px"
            :disabled="executing"
          />
          <span style="color: #999; font-size: 12px">Top K</span>
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
            :disabled="!userQuery.trim() || executing"
          >
            <template #icon><FileTextOutlined /></template>
            执行LLM生成
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

    <!-- 智能检索结果展示 -->
    <a-card 
      v-if="retrievalResult && !executing" 
      title="智能检索结果" 
      style="margin-bottom: 24px"
      :bordered="true"
    >
      <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
        <a-descriptions-item label="阶段1耗时">
          {{ formatTime(retrievalResult.execution_time?.stage1 || 0) }}
        </a-descriptions-item>
        <a-descriptions-item label="阶段2耗时">
          {{ formatTime(retrievalResult.execution_time?.stage2 || 0) }}
        </a-descriptions-item>
        <a-descriptions-item label="总耗时">
          {{ formatTime(retrievalResult.execution_time?.total || 0) }}
        </a-descriptions-item>
        <a-descriptions-item label="精筛结果总数">
          {{ retrievalResult.stage2?.total_count || 0 }}
        </a-descriptions-item>
      </a-descriptions>
      
      <a-collapse v-model:activeKey="retrievalCollapseActiveKey">
        <a-collapse-panel key="stage1" header="阶段1：Milvus快速召回">
          <a-list
            v-if="retrievalResult.stage1?.top3_documents?.length > 0"
            :data-source="retrievalResult.stage1.top3_documents"
            size="small"
          >
            <template #renderItem="{ item, index }">
              <a-list-item>
                <a-space>
                  <a-tag color="blue">文档 {{ index + 1 }}</a-tag>
                  <span>{{ item.document_name || item.group_id }}</span>
                  <a-tag color="orange">相似度: {{ (item.score * 100).toFixed(1) }}%</a-tag>
                </a-space>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="没有找到匹配的文档" />
        </a-collapse-panel>
        
        <a-collapse-panel key="stage2" header="阶段2：精细处理结果">
          <a-list
            v-if="retrievalResult.stage2?.refined_results?.length > 0"
            :data-source="retrievalResult.stage2.refined_results.slice(0, 20)"
            size="small"
            :pagination="{ pageSize: 10, simple: true }"
          >
            <template #renderItem="{ item, index }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                      <a-tag :color="getSourceColor(item.source)">{{ item.source }}</a-tag>
                      <a-tag :color="getTypeColor(item.type)">{{ item.type }}</a-tag>
                      <span>{{ item.name || item.content?.substring(0, 50) }}</span>
                      <a-tag color="orange">相似度: {{ (item.score * 100).toFixed(1) }}%</a-tag>
                    </a-space>
                  </template>
                  <template #description>
                    <div style="color: #666; font-size: 12px; max-height: 60px; overflow: hidden;">
                      {{ item.content?.substring(0, 200) }}{{ item.content?.length > 200 ? '...' : '' }}
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="没有精筛结果" />
        </a-collapse-panel>
      </a-collapse>
    </a-card>

    <!-- LLM生成结果展示 -->
    <div v-if="executionResult && !executing">
      <!-- 生成的新需求文档 -->
      <a-card title="生成的新需求文档" style="margin-bottom: 24px">
        <div 
          v-html="formatMarkdown(executionResult.generated_document)"
          style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; padding: 16px; background: #fafafa; border-radius: 4px; max-height: 600px; overflow-y: auto;"
        ></div>
      </a-card>

      <!-- 对比分析 -->
      <a-card v-if="executionResult.comparison_analysis" title="对比分析" style="margin-bottom: 24px">
        <div 
          v-html="formatMarkdown(executionResult.comparison_analysis)"
          style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; padding: 16px; background: #fafafa; border-radius: 4px; max-height: 400px; overflow-y: auto;"
        ></div>
      </a-card>

      <!-- 复用建议 -->
      <a-card v-if="executionResult.reuse_suggestions" title="复用建议" style="margin-bottom: 24px">
        <a-list
          :data-source="executionResult.reuse_suggestions"
          :pagination="{ pageSize: 5 }"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <a-space>
                    <a-tag color="green">{{ item.type || '建议' }}</a-tag>
                    <span>{{ item.title || item.content }}</span>
                  </a-space>
                </template>
                <template #description>
                  <div v-if="item.content" style="margin-top: 8px; color: #666">
                    {{ item.content }}
                  </div>
                  <div v-if="item.source" style="margin-top: 4px; font-size: 12px; color: #999">
                    来源: {{ item.source }}
                  </div>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </a-card>

      <!-- 风险提示 -->
      <a-card v-if="executionResult.risk_warnings && executionResult.risk_warnings.length > 0" title="风险提示">
        <a-alert
          v-for="(warning, index) in executionResult.risk_warnings"
          :key="index"
          :message="warning.title || '风险提示'"
          :description="warning.content || warning"
          type="warning"
          show-icon
          style="margin-bottom: 12px"
        />
      </a-card>
    </div>

    <!-- 空状态 -->
    <a-empty
      v-else
      description="请输入用户需求，然后点击执行按钮（将自动执行智能检索和LLM生成）"
      style="margin: 60px 0"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { FileTextOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { step7LLMGenerate, smartRetrieval } from '../../api/intelligentChat'
import { SOURCE_CONFIG, TYPE_CONFIG } from './recall/constants'

const userQuery = ref('')
const injectedResultsJson = ref('')
const provider = ref('deepseek')
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)
const retrievalResult = ref(null)
const retrievalCollapseActiveKey = ref(['stage1', 'stage2'])
const retrievalScope = ref('all')
const topK = ref(50)

const loadFromTab6 = () => {
  const tab6Result = localStorage.getItem('intelligent_chat_tab6_result')
  if (tab6Result) {
    try {
      const parsed = JSON.parse(tab6Result)
      injectedResultsJson.value = JSON.stringify(parsed.injected_results || parsed, null, 2)
      message.success('已加载Tab 6的结果')
    } catch (e) {
      message.error('加载Tab 6结果失败，请手动复制')
    }
  } else {
    message.warning('未找到Tab 6的结果，请先执行Tab 6')
  }
}

const handleExecute = async () => {
  if (!userQuery.value.trim()) {
    message.warning('请输入用户需求')
    return
  }

  executing.value = true
  executionStatus.value = '正在执行智能检索...'
  executionResult.value = null
  retrievalResult.value = null

  try {
    // 步骤1: 执行智能检索
    executionStatus.value = '正在执行智能检索...'
    const retrievalParams = {
      query: userQuery.value,
      top_k: topK.value,
      top3: true,
      group_ids: null, // 全部文档
      enable_refine: true,
      enable_bm25: true,
      enable_graph_traverse: true
    }
    
    const retrieval = await smartRetrieval(retrievalParams)
    retrievalResult.value = retrieval
    
    if (!retrieval.success) {
      throw new Error(retrieval.error || '智能检索失败')
    }
    
    if (!retrieval.stage2?.refined_results || retrieval.stage2.refined_results.length === 0) {
      message.warning('智能检索未找到相关结果，将仅使用Mem0上下文生成回答')
    } else {
      message.success(`智能检索完成，找到 ${retrieval.stage2.total_count} 个相关结果`)
    }

    // 步骤2: 解析Mem0注入结果（可选）
    let injectedResults = []
    if (injectedResultsJson.value.trim()) {
      try {
        const parsed = JSON.parse(injectedResultsJson.value)
        if (Array.isArray(parsed)) {
          injectedResults = parsed
        } else if (parsed.injected_results) {
          injectedResults = parsed.injected_results
        } else {
          message.warning('Mem0注入结果格式不正确，将仅使用智能检索结果')
        }
      } catch (e) {
        message.warning('Mem0注入结果JSON格式错误，将仅使用智能检索结果')
      }
    }

    // 步骤3: 执行LLM生成
    executionStatus.value = '正在执行LLM生成...'
    const result = await step7LLMGenerate({
      query: userQuery.value,
      retrieval_results: retrieval.stage2?.refined_results || [], // 智能检索结果
      injected_results: injectedResults, // Mem0上下文（可选）
      provider: provider.value
    })

    executionResult.value = result
    message.success('LLM生成完成')
  } catch (error) {
    console.error('执行失败:', error)
    message.error(`执行失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
    executionResult.value = null
    retrievalResult.value = null
  } finally {
    executing.value = false
    executionStatus.value = ''
  }
}

const handleClear = () => {
  executionResult.value = null
  retrievalResult.value = null
  userQuery.value = ''
  injectedResultsJson.value = ''
  message.success('结果已清空')
}

const formatTime = (seconds) => {
  if (seconds < 1) {
    return `${(seconds * 1000).toFixed(0)}ms`
  }
  return `${seconds.toFixed(2)}s`
}

const getSourceColor = (source) => {
  return SOURCE_CONFIG[source]?.color || 'default'
}

const getTypeColor = (type) => {
  return TYPE_CONFIG[type]?.color || 'default'
}

// 格式化Markdown为HTML（简化版）
const formatMarkdown = (text) => {
  if (!text) return ''
  
  // 转义HTML特殊字符
  const escapeHtml = (str) => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }
  
  let processedText = text
  
  // 处理标题
  processedText = processedText.replace(/^#### (.*$)/gim, '<h4 style="margin: 16px 0 8px 0; font-size: 16px; font-weight: 600;">$1</h4>')
  processedText = processedText.replace(/^### (.*$)/gim, '<h3 style="margin: 20px 0 12px 0; font-size: 18px; font-weight: 600;">$1</h3>')
  processedText = processedText.replace(/^## (.*$)/gim, '<h2 style="margin: 24px 0 16px 0; font-size: 20px; font-weight: 600;">$1</h2>')
  processedText = processedText.replace(/^# (.*$)/gim, '<h1 style="margin: 28px 0 20px 0; font-size: 24px; font-weight: 600;">$1</h1>')
  
  // 处理粗体
  processedText = processedText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  
  // 处理列表
  processedText = processedText.replace(/^[\-\*\+] (.+)$/gim, '<li style="margin: 4px 0;">$1</li>')
  processedText = processedText.replace(/(<li[^>]*>.*?<\/li>(?:\s*<li[^>]*>.*?<\/li>)*)/gs, '<ul style="margin: 8px 0; padding-left: 24px;">$1</ul>')
  
  // 处理换行
  processedText = processedText.replace(/\n\n/g, '<br><br>')
  processedText = processedText.replace(/\n/g, '<br>')
  
  return processedText
}
</script>

<style scoped>
</style>

