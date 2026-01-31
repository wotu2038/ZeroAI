<template>
  <div>
    <!-- 文档选择 -->
    <a-card style="margin-bottom: 16px">
      <a-form layout="inline">
        <a-form-item label="选择文档">
          <a-select
            v-model:value="selectedGroupId"
            placeholder="请选择文档（Group ID）"
            style="width: 400px"
            :loading="loadingDocuments"
            allow-clear
            @change="handleDocumentChange"
          >
            <a-select-option
              v-for="doc in documents"
              :key="doc.group_id"
              :value="doc.group_id"
            >
              {{ doc.group_id }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button @click="loadDocuments">刷新文档列表</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 子Tab页 -->
    <a-tabs v-model:activeKey="activeSubTab" v-if="selectedGroupId">
      <a-tab-pane key="community" tab="Community管理">
        <CommunityManagement :group-id="selectedGroupId" />
      </a-tab-pane>
      
      <a-tab-pane key="episode" tab="Episode管理">
        <EpisodeManagement :group-id="selectedGroupId" />
      </a-tab-pane>
      
      <a-tab-pane key="edge" tab="关系管理">
        <EdgeManagement :group-id="selectedGroupId" />
      </a-tab-pane>
      
      <a-tab-pane key="entity" tab="实体管理">
        <EntityManagement :group-id="selectedGroupId" />
      </a-tab-pane>
    </a-tabs>

    <a-empty
      v-else
      description="请先选择文档（Group ID）"
      style="margin: 60px 0"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { listDocuments } from '../../api/knowledgeManagement'
import CommunityManagement from './CommunityManagement.vue'
import EpisodeManagement from './EpisodeManagement.vue'
import EdgeManagement from './EdgeManagement.vue'
import EntityManagement from './EntityManagement.vue'

const selectedGroupId = ref(null)
const activeSubTab = ref('community')
const documents = ref([])
const loadingDocuments = ref(false)

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await listDocuments()
    documents.value = response || []
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载失败: ${error.message || '未知错误'}`)
  } finally {
    loadingDocuments.value = false
  }
}

const handleDocumentChange = () => {
  // 文档切换时，重置子Tab到第一个
  activeSubTab.value = 'community'
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
</style>

