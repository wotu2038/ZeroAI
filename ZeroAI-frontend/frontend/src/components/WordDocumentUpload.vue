<template>
  <div class="word-document-upload">
    <a-card title="Word 文档上传和处理">
      <a-upload
        :before-upload="handleUpload"
        :file-list="fileList"
        accept=".docx,.doc"
        :max-count="1"
      >
        <a-button type="primary">
          <template #icon><UploadOutlined /></template>
          上传 Word 文档
        </a-button>
        <template #tip>
          <div style="margin-top: 8px; color: #999">
            支持 .docx 和 .doc 格式，文件大小建议不超过 50MB
          </div>
        </template>
      </a-upload>
      
      <!-- 处理进度 -->
      <div v-if="processing" style="margin-top: 16px">
        <a-progress
          :percent="progress"
          :status="progressStatus"
          :stroke-color="progressStatus === 'active' ? { '0%': '#108ee9', '100%': '#87d068' } : undefined"
        />
        <div v-if="progressMessage" style="margin-top: 8px; color: #666; font-size: 14px; font-weight: 500;">
          {{ progressMessage }}
        </div>
        <div v-if="currentStep" style="margin-top: 4px; color: #999; font-size: 12px;">
          当前步骤: {{ currentStep }}
        </div>
        <div v-if="detailedProgress" style="margin-top: 8px; padding: 8px; background: #f5f5f5; border-radius: 4px; font-size: 12px;">
          <div v-for="(item, index) in detailedProgress" :key="index" style="margin: 4px 0;">
            <a-tag :color="item.status === 'completed' ? 'success' : item.status === 'processing' ? 'processing' : 'default'" size="small">
              {{ item.label }}
            </a-tag>
            <span v-if="item.count" style="margin-left: 8px; color: #666;">
              {{ item.count }}
            </span>
          </div>
        </div>
      </div>
      
      <!-- 处理结果 -->
      <a-card
        v-if="result"
        title="处理结果"
        style="margin-top: 16px"
      >
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="文档名称">
            {{ result.document_name }}
          </a-descriptions-item>
          <a-descriptions-item label="文档ID">
            {{ result.document_id }}
          </a-descriptions-item>
          <a-descriptions-item label="章节数">
            <a-tag color="blue">{{ result.statistics.total_sections }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="图片数">
            <a-tag color="green">{{ result.statistics.total_images }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="表格数">
            <a-tag color="orange">{{ result.statistics.total_tables }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="链接数">
            <a-tag color="purple">{{ result.statistics.total_links }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>
        
        <a-divider />
        
        <div>
          <h4>Episode 信息</h4>
          <p>文档级 Episode: <code>{{ result.document_episode_uuid }}</code></p>
          <p>章节级 Episode 数量: {{ result.section_episodes.length }}</p>
          <p v-if="result.image_episodes.length > 0">
            图片 Episode 数量: {{ result.image_episodes.length }}
          </p>
          <p v-if="result.table_episodes.length > 0">
            表格 Episode 数量: {{ result.table_episodes.length }}
          </p>
        </div>
        
        <a-divider />
        
        <div style="text-align: center">
          <a-space>
            <a-button type="primary" @click="handleViewDocument">
              <template #icon><EyeOutlined /></template>
              查看文档详情
            </a-button>
            <a-button @click="handleGoToManagement">
              <template #icon><FileTextOutlined /></template>
              前往文档管理
            </a-button>
          </a-space>
        </div>
      </a-card>
      
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
          
          <a-divider>章节列表</a-divider>
          <a-list
            :data-source="currentDocumentEpisodes.section_episodes"
            size="small"
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
    </a-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { UploadOutlined, EyeOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { uploadWordDocument, getDocumentEpisodes } from '../api/wordDocument'

const router = useRouter()
const fileList = ref([])
const processing = ref(false)
const progress = ref(0)
const progressStatus = ref('active')
const progressMessage = ref('')
const currentStep = ref('')
const detailedProgress = ref([])
const elapsedTime = ref('')
const result = ref(null)
const episodeDrawerVisible = ref(false)
const currentDocumentEpisodes = ref(null)
const loadingEpisodes = ref(false)

const handleUpload = async (file) => {
  fileList.value = [file]
  processing.value = true
  progress.value = 0
  progressStatus.value = 'active'
  progressMessage.value = '开始上传文档...'
  currentStep.value = '上传中'
  detailedProgress.value = [
    { label: '上传文件', status: 'processing', count: null },
    { label: '解析文档', status: 'pending', count: null },
    { label: '创建章节Episode', status: 'pending', count: null },
    { label: '创建图片Episode', status: 'pending', count: null },
    { label: '创建表格Episode', status: 'pending', count: null },
    { label: '生成向量嵌入', status: 'pending', count: null }
  ]
  result.value = null
  
  const startTime = Date.now()
  let elapsedInterval = null
  
  // 更新已用时间
  const updateElapsedTime = () => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000)
    const minutes = Math.floor(elapsed / 60)
    const seconds = elapsed % 60
    elapsedTime.value = `${minutes}分${seconds}秒`
  }
  
  elapsedInterval = setInterval(updateElapsedTime, 1000)
  updateElapsedTime()
  
  try {
    // 模拟进度更新（因为后端是同步处理，无法获取实时进度）
    const progressInterval = setInterval(() => {
      if (progress.value < 90) {
        const elapsed = (Date.now() - startTime) / 1000 // 已用时间（秒）
        
        // 根据进度显示不同的消息
        if (progress.value < 5) {
          progressMessage.value = '正在上传文档...'
          currentStep.value = '上传文件'
          detailedProgress.value[0].status = 'processing'
        } else if (progress.value < 15) {
          progressMessage.value = '正在解析文档结构...'
          currentStep.value = '解析文档'
          detailedProgress.value[0].status = 'completed'
          detailedProgress.value[1].status = 'processing'
        } else if (progress.value < 25) {
          progressMessage.value = '正在提取内容（文本、图片、表格、嵌入文档）...'
          currentStep.value = '提取内容'
          detailedProgress.value[1].status = 'completed'
        } else if (progress.value < 60) {
          progressMessage.value = '正在创建章节Episode并提取实体和关系...'
          currentStep.value = '创建章节Episode'
          detailedProgress.value[2].status = 'processing'
          // 根据时间估算章节进度（假设每个章节需要3-5秒）
          const estimatedSections = Math.min(Math.floor((elapsed - 10) / 4), 50)
          if (estimatedSections > 0) {
            detailedProgress.value[2].count = `约 ${estimatedSections} 个章节`
          }
        } else if (progress.value < 75) {
          progressMessage.value = '正在创建图片Episode...'
          currentStep.value = '创建图片Episode'
          detailedProgress.value[2].status = 'completed'
          detailedProgress.value[3].status = 'processing'
        } else if (progress.value < 85) {
          progressMessage.value = '正在创建表格Episode...'
          currentStep.value = '创建表格Episode'
          detailedProgress.value[3].status = 'completed'
          detailedProgress.value[4].status = 'processing'
        } else {
          progressMessage.value = '正在生成向量嵌入...'
          currentStep.value = '生成嵌入'
          detailedProgress.value[4].status = 'completed'
          detailedProgress.value[5].status = 'processing'
        }
        
        // 根据已用时间动态调整进度增长速度
        // 前30秒快速增长，之后缓慢增长
        if (elapsed < 30) {
          progress.value += Math.random() * 2 + 0.5 // 0.5-2.5%
        } else if (elapsed < 120) {
          progress.value += Math.random() * 1 + 0.2 // 0.2-1.2%
        } else {
          progress.value += Math.random() * 0.5 + 0.1 // 0.1-0.6%
        }
        
        // 确保不超过90%
        if (progress.value > 90) {
          progress.value = 90
        }
      }
    }, 1000) // 每1秒更新一次
    
    const response = await uploadWordDocument(file, 'qianwen', 8000)
    
    clearInterval(progressInterval)
    if (elapsedInterval) {
      clearInterval(elapsedInterval)
      elapsedInterval = null
    }
    progress.value = 100
    progressStatus.value = 'success'
    progressMessage.value = '文档处理完成！'
    currentStep.value = '完成'
    
    // 更新详细进度
    detailedProgress.value.forEach(item => {
      if (item.status === 'processing') {
        item.status = 'completed'
      }
    })
    
    // 显示实际统计
    if (response.section_episodes) {
      detailedProgress.value[2].count = `${response.section_episodes.length} 个章节`
    }
    if (response.image_episodes) {
      detailedProgress.value[3].count = `${response.image_episodes.length} 张图片`
    }
    if (response.table_episodes) {
      detailedProgress.value[4].count = `${response.table_episodes.length} 个表格`
    }
    
    // 注意：api/index.js 的响应拦截器已经返回了 response.data，所以这里直接使用 response
    result.value = response
    
    const totalEpisodes = (response.section_episodes?.length || 0) + 
                         (response.image_episodes?.length || 0) + 
                         (response.table_episodes?.length || 0) + 1 // +1 for document episode
    message.success(`文档处理成功！共创建 ${totalEpisodes} 个Episode（${response.section_episodes?.length || 0} 章节 + ${response.image_episodes?.length || 0} 图片 + ${response.table_episodes?.length || 0} 表格）`)
  } catch (error) {
    progressStatus.value = 'exception'
    progressMessage.value = `处理失败: ${error.message || '未知错误'}`
    currentStep.value = '失败'
    detailedProgress.value.forEach(item => {
      if (item.status === 'processing') {
        item.status = 'error'
      }
    })
    message.error(`处理失败: ${error.message || '未知错误'}`)
  } finally {
    processing.value = false
    if (elapsedInterval) {
      clearInterval(elapsedInterval)
      elapsedInterval = null
    }
    // 延迟清除进度消息
    setTimeout(() => {
      progressMessage.value = ''
      currentStep.value = ''
      elapsedTime.value = ''
      detailedProgress.value = []
    }, 5000)
  }
  
  return false // 阻止自动上传
}

const handleViewDocument = async () => {
  if (!result.value?.document_id) {
    message.warning('请先上传文档')
    return
  }
  
  episodeDrawerVisible.value = true
  loadingEpisodes.value = true
  currentDocumentEpisodes.value = null
  
  try {
    const response = await getDocumentEpisodes(result.value.document_id, false, 'qianwen')
    // 注意：api/index.js 的响应拦截器已经返回了 response.data，所以这里直接使用 response
    currentDocumentEpisodes.value = response
  } catch (error) {
    message.error(`获取 Episode 信息失败: ${error.message || '未知错误'}`)
  } finally {
    loadingEpisodes.value = false
  }
}

const handleGoToManagement = () => {
  router.push({ name: 'requirements-management', query: { tab: 'document-management' } })
}
</script>

<style scoped>
.word-document-upload {
  max-width: 1200px;
}
</style>

