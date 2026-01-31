<template>
  <div class="similar-requirement-search">
    <a-card title="相似需求搜索">
      <!-- 搜索输入 -->
      <a-space direction="vertical" style="width: 100%" size="large">
        <a-input-group compact>
          <a-input
            v-model:value="searchText"
            placeholder="输入新需求描述..."
            style="width: calc(100% - 200px)"
            @pressEnter="handleSearch"
          />
          <a-button type="primary" @click="handleSearch" :loading="searching">
            搜索相似需求
          </a-button>
        </a-input-group>
        
        <!-- 或上传文档 -->
        <div>
          <span style="color: #999; margin-right: 8px">或</span>
          <a-upload
            :before-upload="handleDocumentUpload"
            accept=".docx,.doc"
            :show-upload-list="false"
          >
            <a-button>
              <template #icon><UploadOutlined /></template>
              上传需求文档
            </a-button>
          </a-upload>
        </div>
      </a-space>
      
      <!-- 搜索结果 -->
      <a-list
        v-if="results.length > 0"
        :data-source="results"
        style="margin-top: 24px"
        :loading="searching"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <span>{{ item.requirement.name }}</span>
                  <a-tag color="blue">
                    相似度: {{ (item.similarity_score * 100).toFixed(1) }}%
                  </a-tag>
                </a-space>
              </template>
              <template #description>
                <div>
                  <p style="margin-bottom: 8px">
                    {{ item.requirement.description || item.requirement.content?.substring(0, 200) || '无描述' }}
                  </p>
                  <div style="margin-top: 8px">
                    <a-tag v-if="item.semantic_score" color="green" style="margin-right: 8px">
                      语义相似度: {{ (item.semantic_score * 100).toFixed(1) }}%
                    </a-tag>
                    <a-tag v-if="item.feature_overlap_ratio" color="orange" style="margin-right: 8px">
                      功能点重合: {{ (item.feature_overlap_ratio * 100).toFixed(1) }}%
                    </a-tag>
                    <a-tag v-if="item.module_overlap_ratio" color="purple">
                      模块重合: {{ (item.module_overlap_ratio * 100).toFixed(1) }}%
                    </a-tag>
                  </div>
                  <div v-if="item.common_features && item.common_features.length > 0" style="margin-top: 8px">
                    <span style="font-weight: bold; margin-right: 8px">共同功能点：</span>
                    <a-tag
                      v-for="feature in item.common_features"
                      :key="feature"
                      style="margin-right: 4px"
                    >
                      {{ feature }}
                    </a-tag>
                  </div>
                  <div v-if="item.common_modules && item.common_modules.length > 0" style="margin-top: 8px">
                    <span style="font-weight: bold; margin-right: 8px">共同模块：</span>
                    <a-tag
                      v-for="module in item.common_modules"
                      :key="module"
                      color="purple"
                      style="margin-right: 4px"
                    >
                      {{ module }}
                    </a-tag>
                  </div>
                </div>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a-button type="link" @click="handleViewRequirement(item.requirement.id)">
                查看详情
              </a-button>
            </template>
          </a-list-item>
        </template>
      </a-list>
      
      <!-- 空状态 -->
      <a-empty
        v-else-if="!searching && hasSearched"
        description="未找到相似需求"
        style="margin-top: 48px"
      />
    </a-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import { findSimilarRequirements } from '../api/requirements'
import { uploadWordDocument } from '../api/wordDocument'

const searchText = ref('')
const searching = ref(false)
const hasSearched = ref(false)
const results = ref([])

const handleSearch = async () => {
  if (!searchText.value.trim()) {
    message.warning('请输入搜索内容')
    return
  }
  
  searching.value = true
  hasSearched.value = true
  results.value = []
  
  try {
    const response = await findSimilarRequirements({
      query_text: searchText.value,
      limit: 10,
      include_features: true,
      include_modules: true
    }, 'qianwen')
    
    results.value = response.data.results || []
    
    if (results.value.length === 0) {
      message.info('未找到相似需求')
    } else {
      message.success(`找到 ${results.value.length} 个相似需求`)
    }
  } catch (error) {
    message.error(`搜索失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    searching.value = false
  }
}

const handleDocumentUpload = async (file) => {
  try {
    message.loading('正在处理文档...', 0)
    
    // 先上传文档
    const uploadResponse = await uploadWordDocument(file, 'qianwen', 8000)
    
    // 从文档中提取文本进行搜索（这里简化处理，实际应该从文档内容中提取）
    // 暂时使用文档名称作为搜索文本
    searchText.value = uploadResponse.data.document_name
    
    message.destroy()
    message.success('文档处理完成，开始搜索相似需求')
    
    // 执行搜索
    await handleSearch()
  } catch (error) {
    message.destroy()
    message.error(`处理失败: ${error.response?.data?.detail || error.message}`)
  }
  
  return false // 阻止自动上传
}

const handleViewRequirement = (requirementId) => {
  // 跳转到需求详情页面（需要实现）
  message.info(`查看需求 ${requirementId} 的详情`)
}
</script>

<style scoped>
.similar-requirement-search {
  max-width: 1200px;
}
</style>

