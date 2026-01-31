<template>
  <div class="recall-results">
    <!-- 统计卡片 -->
    <RecallStatisticsCard :result="result" />

    <!-- 结果列表 -->
    <a-card title="召回结果列表" class="results-card">
      <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
        <a-tab-pane 
          key="graphiti" 
          :tab="`Graphiti (${result.graphiti_count || 0})`"
        >
          <RecallResultList 
            :results="result.graphiti_results || []"
            source="graphiti"
          />
        </a-tab-pane>
        
        <a-tab-pane 
          key="cognee" 
          :tab="`Cognee (${result.cognee_count || 0})`"
        >
          <RecallResultList 
            :results="result.cognee_results || []"
            source="cognee"
          />
        </a-tab-pane>
        
        <a-tab-pane 
          key="milvus" 
          :tab="`Milvus (${result.milvus_count || 0})`"
        >
          <RecallResultList 
            :results="result.milvus_results || []"
            source="milvus"
          />
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import RecallStatisticsCard from './RecallStatisticsCard.vue'
import RecallResultList from '../RecallResultList.vue'

const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

const activeTab = ref('graphiti')

const handleTabChange = (key) => {
  activeTab.value = key
  // 可以触发父组件事件
}
</script>

<style scoped>
.recall-results {
  width: 100%;
}

.results-card {
  margin-top: 24px;
}
</style>

