<template>
  <div class="discover-container">
    <!-- 顶部标题和搜索 -->
    <div class="discover-header">
      <h1 class="discover-title">发现</h1>
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索共享知识库"
        style="width: 300px"
        :loading="loading"
        @search="handleSearch"
        @pressEnter="handleSearch"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input-search>
    </div>

    <!-- 分类标签 -->
    <div class="category-tabs">
      <a-tag
        v-for="cat in categories"
        :key="cat.value"
        :color="currentCategory === cat.value ? 'blue' : 'default'"
        class="category-tag"
        @click="handleCategoryChange(cat.value)"
        style="cursor: pointer; margin-right: 8px; margin-bottom: 8px; padding: 4px 12px; font-size: 14px"
      >
        {{ cat.label }}
      </a-tag>
    </div>

    <!-- 知识库卡片网格 -->
    <div class="knowledge-base-grid" v-if="!loading && knowledgeBases.length > 0">
      <div
        v-for="kb in knowledgeBases"
        :key="kb.id"
        class="kb-card"
      >
        <div class="kb-card-header">
          <div class="kb-icon">
            <component :is="getIconComponent(kb.cover_icon)" v-if="kb.cover_icon" />
            <FolderOutlined v-else />
          </div>
          <a-button
            v-if="currentCategory === 'recommended'"
            type="text"
            size="small"
            class="refresh-btn"
            @click="handleRefresh(kb.id)"
            title="换一换"
          >
            <ReloadOutlined />
          </a-button>
        </div>
        <div class="kb-card-body">
          <h3 class="kb-title">{{ kb.name }}</h3>
          <p class="kb-description">{{ kb.description || '暂无描述' }}</p>
          <div class="kb-stats">
            <span>{{ kb.member_count }}人已加入</span>
            <span class="divider">|</span>
            <span>{{ kb.document_count }}个内容</span>
            <span v-if="kb.creator_name" class="creator">
              | @{{ kb.creator_name }}
            </span>
          </div>
        </div>
        <div class="kb-card-footer">
          <a-button
            v-if="!kb.is_member"
            type="primary"
            block
            @click="handleJoin(kb)"
          >
            加入
          </a-button>
          <a-button
            v-else
            block
            disabled
          >
            已加入
          </a-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <a-empty
      v-if="!loading && knowledgeBases.length === 0"
      description="暂无知识库"
      style="margin-top: 60px"
    />

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <!-- 分页 -->
    <div class="pagination-container" v-if="!loading && knowledgeBases.length > 0">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :show-size-changer="true"
        :page-size-options="['12', '24', '48']"
        @change="handlePageChange"
        @showSizeChange="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  FolderOutlined,
  ReloadOutlined,
  BookOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  TeamOutlined,
  RocketOutlined,
  BulbOutlined,
  CodeOutlined,
  BankOutlined,
  MedicineBoxOutlined,
  SafetyOutlined,
  ReadOutlined,
  HomeOutlined
} from '@ant-design/icons-vue'
import { discoverKnowledgeBases, joinKnowledgeBase } from '@/api/knowledgeBase'

// 分类列表
const categories = [
  { label: '推荐', value: 'recommended' },
  { label: '科技', value: '科技' },
  { label: '教育', value: '教育' },
  { label: '职场', value: '职场' },
  { label: '财经', value: '财经' },
  { label: '产业', value: '产业' },
  { label: '健康', value: '健康' },
  { label: '法律', value: '法律' },
  { label: '人文', value: '人文' },
  { label: '生活', value: '生活' }
]

const loading = ref(false)
const searchKeyword = ref('')
const currentCategory = ref('recommended')
const knowledgeBases = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 12,
  total: 0
})

// 图标映射
const iconMap = {
  'folder': FolderOutlined,
  'book': BookOutlined,
  'file': FileTextOutlined,
  'database': DatabaseOutlined,
  'team': TeamOutlined,
  'rocket': RocketOutlined,
  'bulb': BulbOutlined,
  'code': CodeOutlined,
  'bank': BankOutlined,
  'medicine': MedicineBoxOutlined,
  'safety': SafetyOutlined,
  'read': ReadOutlined,
  'home': HomeOutlined
}

const getIconComponent = (iconName) => {
  return iconMap[iconName] || FolderOutlined
}

// 加载知识库列表
const loadKnowledgeBases = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    if (currentCategory.value !== 'recommended') {
      params.category = currentCategory.value
    }
    
    const res = await discoverKnowledgeBases(params)
    knowledgeBases.value = res.knowledge_bases || []
    pagination.total = res.total || 0
  } catch (error) {
    let errorMsg = '未知错误'
    if (error?.response?.data) {
      if (typeof error.response.data === 'string') {
        errorMsg = error.response.data
      } else if (error.response.data.detail) {
        errorMsg = Array.isArray(error.response.data.detail) 
          ? error.response.data.detail.map(d => d.msg || d).join(', ')
          : error.response.data.detail
      } else {
        errorMsg = JSON.stringify(error.response.data)
      }
    } else if (error?.message) {
      errorMsg = error.message
    }
    message.error('加载知识库失败: ' + errorMsg)
    console.error('发现页面加载失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadKnowledgeBases()
}

// 分类切换
const handleCategoryChange = (category) => {
  currentCategory.value = category
  pagination.current = 1
  loadKnowledgeBases()
}

// 分页变化
const handlePageChange = () => {
  loadKnowledgeBases()
}

// 加入知识库
const handleJoin = async (kb) => {
  try {
    await joinKnowledgeBase(kb.id)
    message.success('加入成功')
    // 更新当前知识库的加入状态
    kb.is_member = true
    // 重新加载列表以更新成员数
    loadKnowledgeBases()
  } catch (error) {
    message.error('加入失败: ' + (error.message || '未知错误'))
  }
}

// 换一换（随机推荐）
const handleRefresh = async (currentKbId) => {
  // 重新加载当前页，实现"换一换"效果
  loadKnowledgeBases()
}

onMounted(() => {
  loadKnowledgeBases()
})
</script>

<style scoped>
.discover-container {
  padding: 24px;
  background: #f0f2f5;
  min-height: calc(100vh - 64px);
}

.discover-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.discover-title {
  font-size: 28px;
  font-weight: bold;
  margin: 0;
}

.category-tabs {
  margin-bottom: 24px;
  padding: 16px 0;
  border-bottom: 1px solid #e8e8e8;
}

.knowledge-base-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.kb-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
}

.kb-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.kb-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.kb-icon {
  font-size: 32px;
  color: #1890ff;
}

.refresh-btn {
  opacity: 0.6;
}

.refresh-btn:hover {
  opacity: 1;
}

.kb-card-body {
  flex: 1;
  margin-bottom: 16px;
}

.kb-title {
  font-size: 18px;
  font-weight: bold;
  margin: 0 0 8px 0;
  color: #262626;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-description {
  font-size: 14px;
  color: #8c8c8c;
  margin: 0 0 12px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 42px;
}

.kb-stats {
  font-size: 12px;
  color: #8c8c8c;
  display: flex;
  align-items: center;
  gap: 4px;
}

.divider {
  margin: 0 4px;
}

.creator {
  color: #1890ff;
}

.kb-card-footer {
  margin-top: auto;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

@media (max-width: 1200px) {
  .knowledge-base-grid {
    grid-template-columns: 1fr;
  }
}
</style>

