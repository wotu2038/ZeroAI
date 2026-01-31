<template>
  <div class="document-list-test">
    <a-card title="文档列表测试（新Tab）">
      <a-space direction="vertical" style="width: 100%">
        <a-alert
          message="这是新的测试Tab页"
          description="用于测试文档列表API调用，绕过可能的缓存问题"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />
        
        <a-button type="primary" @click="loadDocuments" :loading="loading">
          加载文档列表
        </a-button>
        
        <a-divider />
        
        <div v-if="error" style="color: red; margin-bottom: 16px">
          <strong>错误信息：</strong>{{ error }}
        </div>
        
        <a-table
          v-if="documents.length > 0"
          :columns="columns"
          :data-source="documents"
          :pagination="false"
          row-key="document_id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'statistics'">
              <a-space>
                <a-tag color="blue">{{ record.statistics?.total_sections || 0 }} 章节</a-tag>
                <a-tag color="green">{{ record.statistics?.total_images || 0 }} 图片</a-tag>
                <a-tag color="orange">{{ record.statistics?.total_tables || 0 }} 表格</a-tag>
              </a-space>
            </template>
          </template>
        </a-table>
        
        <a-empty v-else-if="!loading && !error" description="暂无数据，点击上方按钮加载" />
        
        <a-descriptions v-if="debugInfo" title="调试信息" bordered style="margin-top: 16px" :column="1">
          <a-descriptions-item label="API Base URL">{{ debugInfo.baseURL }}</a-descriptions-item>
          <a-descriptions-item label="请求URL">{{ debugInfo.requestUrl }}</a-descriptions-item>
          <a-descriptions-item label="响应状态">{{ debugInfo.status }}</a-descriptions-item>
          <a-descriptions-item label="文档数量">{{ debugInfo.documentCount }}</a-descriptions-item>
        </a-descriptions>
      </a-space>
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import api from '../api/index'
import { getDocumentList } from '../api/wordDocument'

const documents = ref([])
const loading = ref(false)
const error = ref(null)
const debugInfo = ref(null)

const columns = [
  {
    title: '文档名称',
    dataIndex: 'document_name',
    key: 'document_name'
  },
  {
    title: '文档ID',
    dataIndex: 'document_id',
    key: 'document_id',
    width: 200
  },
  {
    title: '统计信息',
    key: 'statistics',
    width: 200
  }
]

const loadDocuments = async () => {
  loading.value = true
  error.value = null
  documents.value = []
  debugInfo.value = null
  
  try {
    // 记录调试信息
    const baseURL = api.defaults.baseURL || '/api'
    const requestUrl = `${baseURL}/word-document/?provider=qianwen&limit=10&offset=0`
    
    console.log('🔍 调试信息：')
    console.log('  baseURL:', baseURL)
    console.log('  完整请求URL:', requestUrl)
    console.log('  axios实例:', api)
    
    // 直接使用api实例测试（注意：添加尾部斜杠避免307重定向）
    const response = await api.get('/word-document/', {
      params: {
        provider: 'qianwen',
        limit: 10,
        offset: 0
      }
    })
    
    console.log('✅ API响应:', response)
    
    // 注意：api/index.js 的响应拦截器已经返回了 response.data
    if (response && typeof response === 'object') {
      documents.value = response.documents || []
      debugInfo.value = {
        baseURL: baseURL,
        requestUrl: requestUrl,
        status: 'success',
        documentCount: documents.value.length
      }
      message.success(`成功加载 ${documents.value.length} 个文档`)
    } else {
      throw new Error('响应格式异常: ' + JSON.stringify(response))
    }
  } catch (err) {
    console.error('❌ 加载文档列表错误:', err)
    error.value = err.message || err.toString()
    debugInfo.value = {
      baseURL: api.defaults.baseURL || '/api',
      requestUrl: `${api.defaults.baseURL || '/api'}/word-document/?provider=qianwen&limit=10&offset=0`,
      status: 'error',
      error: error.value
    }
    message.error(`加载失败: ${error.value}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  console.log('📋 DocumentListTest 组件已挂载')
  console.log('  API实例 baseURL:', api.defaults.baseURL)
  // 自动加载一次
  loadDocuments()
})
</script>

<style scoped>
.document-list-test {
  padding: 16px;
}
</style>

