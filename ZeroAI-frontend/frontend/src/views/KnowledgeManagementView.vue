<template>
  <a-card>
    <template #title>
      <span>知识管理</span>
    </template>
    
    <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
      <!-- Tab 1: Group管理 -->
      <a-tab-pane key="group" tab="Group管理">
        <GroupManagement />
      </a-tab-pane>
      
      <!-- Tab 2: Community管理 -->
      <a-tab-pane key="community" tab="Community管理">
        <CommunityManagement />
      </a-tab-pane>
      
      <!-- Tab 3: Episode管理 -->
      <a-tab-pane key="episode" tab="Episode管理">
        <EpisodeManagement />
      </a-tab-pane>
      
      <!-- Tab 4: 关系管理 -->
      <a-tab-pane key="edge" tab="关系管理">
        <EdgeManagement />
      </a-tab-pane>
      
      <!-- Tab 5: 实体管理 -->
      <a-tab-pane key="entity" tab="实体管理">
        <EntityManagement />
      </a-tab-pane>
      
      <!-- Tab 6: 综合管理 -->
      <a-tab-pane key="composite" tab="综合管理">
        <CompositeManagementTab />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import GroupManagement from '../components/knowledge/GroupManagement.vue'
import CommunityManagement from '../components/knowledge/CommunityManagement.vue'
import EpisodeManagement from '../components/knowledge/EpisodeManagement.vue'
import EdgeManagement from '../components/knowledge/EdgeManagement.vue'
import EntityManagement from '../components/knowledge/EntityManagement.vue'
import CompositeManagementTab from '../components/knowledge/CompositeManagementTab.vue'

const activeTab = ref('group')

const handleTabChange = (key) => {
  activeTab.value = key
}

// 监听跳转事件
const handleJumpToTab = (event) => {
  const { tabKey, groupId } = event.detail
  activeTab.value = tabKey
  
  // 延迟设置筛选条件，确保组件已加载
  setTimeout(() => {
    // 触发子组件的筛选条件设置
    window.dispatchEvent(new CustomEvent('set-group-filter', {
      detail: { groupId }
    }))
  }, 100)
}

onMounted(() => {
  window.addEventListener('jump-to-tab', handleJumpToTab)
})

onUnmounted(() => {
  window.removeEventListener('jump-to-tab', handleJumpToTab)
})
</script>

<style scoped>
</style>

