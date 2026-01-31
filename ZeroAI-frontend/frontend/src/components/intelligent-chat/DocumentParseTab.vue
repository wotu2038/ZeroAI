<template>
  <div>
    <!-- 配置区域 -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
      <a-form-item label="选择文档">
        <a-select
          v-model:value="selectedDocumentId"
          placeholder="请选择要解析的文档"
          style="width: 100%"
          :loading="loadingDocuments"
          :disabled="loadingDocuments || executing"
          @change="handleDocumentChange"
          allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.id"
            :value="doc.id"
          >
            {{ doc.file_name }} {{ doc.source === 'library' ? '[文档库]' : '' }} (ID: {{ doc.id }}) - {{ getStatusText(doc.status) }}
          </a-select-option>
        </a-select>
        <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
          没有可用的文档，请先在"文档管理"中上传文档
        </div>
      </a-form-item>

      <a-form-item label="解析配置">
        <a-space>
          <span style="color: #666">每个章节的最大token数：</span>
          <a-input-number
            v-model:value="maxTokensPerSection"
            :min="1000"
            :max="20000"
            :step="1000"
            :disabled="executing"
            style="width: 150px"
          />
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
            :disabled="!selectedDocumentId || executing"
          >
            <template #icon><PlayCircleOutlined /></template>
            执行文档解析
          </a-button>
          <a-button @click="handleClear" :disabled="executing">
            清空结果
          </a-button>
          <a-button @click="loadDocuments" :loading="loadingDocuments">
            <template #icon><ReloadOutlined /></template>
            刷新列表
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
      <a-card title="解析结果" style="margin-bottom: 24px">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="文档名称">
            {{ executionResult.file_name || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="文档ID">
            {{ executionResult.upload_id || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="章节数">
            <a-tag color="blue">{{ executionResult.statistics?.total_sections || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="图片数">
            <a-tag color="green">{{ executionResult.statistics?.total_images || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="表格数">
            <a-tag color="orange">{{ executionResult.statistics?.total_tables || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="字符数">
            {{ executionResult.parsed_content?.length || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="解析状态">
            <a-tag color="green">成功</a-tag>
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 解析内容预览 -->
      <a-card title="解析内容预览">
        <a-tabs v-model:activeKey="contentViewTab">
          <!-- Tab 1: 原始文档 -->
          <a-tab-pane key="original" tab="原始文档">
            <div style="margin-top: 16px">
              <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div style="color: #666; font-size: 12px;">
                  <span v-if="executionResult?.file_name">文件名: {{ executionResult.file_name }}</span>
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

          <!-- Tab 2: 完整对应文档 -->
          <a-tab-pane key="parsed" tab="完整对应文档">
            <div
              v-if="executionResult.parsed_content"
              style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
              v-html="formatMarkdown(executionResult.parsed_content, executionResult.document_id, executionResult.upload_id)"
            ></div>
            <a-empty v-else description="解析内容不可用" />
          </a-tab-pane>

          <!-- Tab 3: 总结文档 -->
          <a-tab-pane key="summary" tab="总结文档" :disabled="!executionResult.summary_content">
            <div
              v-if="executionResult.summary_content"
              style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
              v-html="formatMarkdown(executionResult.summary_content, executionResult.document_id, executionResult.upload_id)"
            ></div>
            <a-empty v-else description="总结文档暂不可用" />
          </a-tab-pane>

          <!-- Tab 4: 结构化数据 -->
          <a-tab-pane key="structured" tab="结构化数据" :disabled="!executionResult.structured_content || executionResult.structured_content.length === 0">
            <div v-if="executionResult.structured_content && executionResult.structured_content.length > 0">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a-button size="small" type="primary" ghost @click="downloadStructured">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
              </div>
              <pre
                style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;"
              >{{ JSON.stringify(executionResult.structured_content, null, 2) }}</pre>
            </div>
            <a-empty v-else description="结构化数据暂不可用" />
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </div>

    <!-- 空状态 -->
    <a-empty
      v-else
      description="请选择文档并点击'执行文档解析'按钮"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, LoadingOutlined, ReloadOutlined, DownloadOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getDocumentUploadList, parseDocument, uploadDocument } from '../../api/documentUpload'
import { getDocuments as getLibraryDocuments, getDocument } from '../../api/documentLibrary'

const documents = ref([])
const loadingDocuments = ref(false)
const selectedDocumentId = ref(null)
const maxTokensPerSection = ref(8000)
const executing = ref(false)
const executionStatus = ref('')
const executionResult = ref(null)
const contentViewTab = ref('original')
const wordDocumentHtml = ref(null)
const loadingWordDocument = ref(false)

const getStatusText = (status) => {
  const statusMap = {
    validated: '已验证',
    parsing: '解析中',
    parsed: '已解析',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    // 同时从 document-upload 和 document-library 加载文档
    const [uploadResponse, libraryResponse] = await Promise.all([
      getDocumentUploadList(1, 100, null, null).catch(() => ({ documents: [] })),
      getLibraryDocuments({ page: 1, page_size: 100 }).catch(() => ({ data: { items: [] } }))
    ])
    
    const uploadDocs = uploadResponse && uploadResponse.documents ? uploadResponse.documents : []
    const libraryDocs = libraryResponse && libraryResponse.data && libraryResponse.data.items 
      ? libraryResponse.data.items.map(doc => ({
          id: `library_${doc.id}`, // 添加前缀区分来源
          library_id: doc.id, // 保存原始 library ID
          file_name: doc.original_name || doc.file_name,
          file_size: doc.file_size,
          file_path: doc.file_path,
          status: doc.status || 'unassigned',
          source: 'library' // 标记来源
        }))
      : []
    
    // 合并两个列表
    documents.value = [...uploadDocs, ...libraryDocs]
    
    if (documents.value.length === 0) {
      console.warn('文档列表为空')
    } else {
      console.log(`加载了 ${uploadDocs.length} 个上传文档和 ${libraryDocs.length} 个文档库文档`)
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
  wordDocumentHtml.value = null
  contentViewTab.value = 'original'
}

const handleExecute = async () => {
  if (!selectedDocumentId.value) {
    message.warning('请先选择文档')
    return
  }

  const selectedDoc = documents.value.find((d) => d.id === selectedDocumentId.value)
  if (!selectedDoc) {
    message.error('文档不存在')
    return
  }

  executing.value = true
  executionStatus.value = '正在解析文档...'
  executionResult.value = null

  try {
    let uploadId = selectedDocumentId.value
    
    // 如果选择的是文档库的文档，需要先创建 document-upload 记录
    if (selectedDoc.source === 'library') {
      message.info('正在从文档库创建解析任务...')
      
      try {
        // 获取文档库文档的详细信息
        const libraryDoc = await getDocument(selectedDoc.library_id)
        
        // 读取文件并上传到 document-upload
        const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'
        const token = localStorage.getItem('token') || sessionStorage.getItem('token')
        
        const fileResponse = await fetch(`${apiBase}/document-library/documents/${selectedDoc.library_id}/download`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        if (!fileResponse.ok) {
          throw new Error('无法下载文档库文件')
        }
        
        const blob = await fileResponse.blob()
        const fileName = libraryDoc.data?.original_name || libraryDoc.data?.file_name || `document_${selectedDoc.library_id}.docx`
        const file = new File([blob], fileName, { type: blob.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
        
        // 上传到 document-upload
        const uploadResponse = await uploadDocument(file)
        uploadId = uploadResponse.id
        
        message.success('已从文档库创建解析任务')
        
        // 重新加载文档列表
        await loadDocuments()
      } catch (error) {
        console.error('从文档库创建任务失败:', error)
        message.error(`从文档库创建任务失败: ${error.message || '未知错误'}`)
        return
      }
    }
    
    message.info('开始解析文档...')
    const result = await parseDocument(uploadId, maxTokensPerSection.value)
    executionResult.value = result
    message.success('文档解析完成！')
    contentViewTab.value = 'original'
    wordDocumentHtml.value = null
  } catch (error) {
    console.error('解析文档失败:', error)
    message.error(`解析失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    executing.value = false
    executionStatus.value = ''
  }
}

const handleClear = () => {
  executionResult.value = null
  wordDocumentHtml.value = null
  contentViewTab.value = 'original'
  message.success('结果已清空')
}

// Markdown格式化函数（与文档管理页面逻辑保持一致的简化版）
const formatMarkdown = (text, documentId = null, uploadId = null) => {
  if (!text) return ''

  // 将 /api/word-document/{document_id}/ 转换为 /api/document-upload/{upload_id}/
  if (uploadId && documentId) {
    text = text.replace(/\/api\/word-document\/([^/]+)\/images\/([^)]+)/g, (match, docId, imageId) => {
      if (docId === documentId) {
        return `/api/document-upload/${uploadId}/images/${imageId}`
      }
      return match
    })

    text = text.replace(/\/api\/word-document\/([^/]+)\/ole\/([^?\s)]+)(\?[^)\s]*)?/g, (match, docId, oleId, query) => {
      if (docId === documentId) {
        return `/api/document-upload/${uploadId}/ole/${oleId}${query || ''}`
      }
      return match
    })
  }

  // 处理图片和嵌入文档
  if (uploadId) {
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
      if (url.startsWith('/api/document-upload/')) {
        return match
      } else if (url.includes('images/')) {
        const imageId = url.split('images/')[1] || url
        const fullUrl = `/api/document-upload/${uploadId}/images/${imageId}`
        return `![${alt}](${fullUrl})`
      }
      return match
    })
  }

  return text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      if (url.includes('/images/') || (url.startsWith('/api/document-upload/') && url.includes('images/'))) {
        return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
      }
      return `<a href="${url}" target="_blank">${linkText}</a>`
    })
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

// 加载Word文档并转换为HTML
const loadWordDocument = async () => {
  if (!executionResult.value?.upload_id) {
    message.warning('文档ID不存在，请先解析文档')
    return
  }

  loadingWordDocument.value = true
  wordDocumentHtml.value = null

  try {
    const documentId = `upload_${executionResult.value.upload_id}`
    const previewUrl = `/api/word-document/${documentId}/preview?provider=qianwen`

    const response = await fetch(previewUrl)
    if (!response.ok) {
      const errorText = await response.text()
      console.error('API响应错误:', response.status, errorText)
      throw new Error(`加载失败: ${response.statusText}`)
    }

    const html = await response.text()
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const bodyContent = doc.body ? doc.body.innerHTML : html
    wordDocumentHtml.value = bodyContent || html

    message.success('Word文档加载成功')
  } catch (error) {
    console.error('加载Word文档失败:', error)
    message.error(`加载Word文档失败: ${error.message || '未知错误'}`)
  } finally {
    loadingWordDocument.value = false
  }
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
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


