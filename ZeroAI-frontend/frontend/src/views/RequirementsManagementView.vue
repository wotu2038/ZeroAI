<template>
  <div class="requirements-management">
    <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
      <!-- Tab 1: Word 文档上传 -->
      <a-tab-pane key="upload" tab="文档上传">
        <WordDocumentUpload />
      </a-tab-pane>
      
      <!-- Tab 2: 相似需求搜索 -->
      <a-tab-pane key="search" tab="相似需求搜索">
        <SimilarRequirementSearch />
      </a-tab-pane>
      
      <!-- Tab 3: 文档管理 -->
      <a-tab-pane key="documents" tab="文档管理">
        <DocumentManagement />
      </a-tab-pane>
      
      <!-- Tab 4: 文档列表测试（新） -->
      <a-tab-pane key="documents-test" tab="文档列表测试">
        <DocumentListTest />
      </a-tab-pane>
      
      <!-- Tab 5: 图谱查找 -->
      <a-tab-pane key="graph-search" tab="图谱查找">
        <GraphSearch />
      </a-tab-pane>
      
      <!-- Tab 6: 组合管理 -->
      <a-tab-pane key="composite-management" tab="组合管理">
        <CompositeManagement />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WordDocumentUpload from '../components/WordDocumentUpload.vue'
import SimilarRequirementSearch from '../components/SimilarRequirementSearch.vue'
import DocumentManagement from '../components/DocumentManagement.vue'
import DocumentListTest from '../components/DocumentListTest.vue'
import GraphSearch from '../components/GraphSearch.vue'
import CompositeManagement from '../components/CompositeManagement.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref('upload')

// 从路由查询参数中获取tab
onMounted(() => {
  const tab = route.query.tab
  if (tab === 'document-management' || tab === 'documents') {
    activeTab.value = 'documents'
  } else if (tab === 'documents-test') {
    activeTab.value = 'documents-test'
  } else if (tab === 'search') {
    activeTab.value = 'search'
  } else if (tab === 'graph-search') {
    activeTab.value = 'graph-search'
  } else if (tab === 'composite-management') {
    activeTab.value = 'composite-management'
  } else {
    activeTab.value = 'upload'
  }
})

const handleTabChange = (key) => {
  activeTab.value = key
  // 更新路由查询参数
  const tabMap = {
    'documents': 'document-management',
    'documents-test': 'documents-test',
    'search': 'search',
    'upload': 'upload',
    'graph-search': 'graph-search',
    'composite-management': 'composite-management'
  }
  router.replace({ query: { tab: tabMap[key] || key } })
}
</script>

<style scoped>
.requirements-management {
  background: #fff;
  padding: 24px;
  min-height: calc(100vh - 112px);
}
</style>

