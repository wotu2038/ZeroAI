<template>
  <a-card>
    <template #title>
      <span>智能对话</span>
    </template>
    
    <a-tabs v-model:activeKey="activeTab">
      <!-- Tab 1: 文档解析 -->
      <a-tab-pane key="document-parse" tab="文档解析">
        <DocumentParseTab />
      </a-tab-pane>

      <!-- Tab 2: Cognee章节级处理 -->
      <a-tab-pane key="cognee" tab="Cognee章节级处理">
        <CogneeTab />
      </a-tab-pane>

      <!-- Tab 3: Graphiti文档级处理 -->
      <a-tab-pane key="graphiti" tab="Graphiti文档级处理">
        <GraphitiTab />
      </a-tab-pane>

      <!-- Tab 4: Milvus向量化处理 -->
      <a-tab-pane key="milvus" tab="Milvus向量化处理">
        <MilvusVectorizeTab />
      </a-tab-pane>

      <!-- Tab 5: 智能检索 -->
      <a-tab-pane key="smart-retrieval" tab="智能检索">
        <SmartRetrievalTab />
      </a-tab-pane>

      <!-- Tab 6: Mem0记忆注入 -->
      <a-tab-pane key="mem0-inject" tab="Mem0记忆注入">
        <Mem0InjectTab />
      </a-tab-pane>

      <!-- Tab 7: LLM生成 -->
      <a-tab-pane key="llm-generate" tab="LLM生成">
        <LLMGenerateTab />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup>
import { ref } from 'vue'
import DocumentParseTab from '../components/intelligent-chat/DocumentParseTab.vue'
import GraphitiTab from '../components/intelligent-chat/GraphitiTab.vue'
import CogneeTab from '../components/intelligent-chat/CogneeTab.vue'
import MilvusVectorizeTab from '../components/intelligent-chat/MilvusVectorizeTab.vue'
import SmartRetrievalTab from '../components/intelligent-chat/SmartRetrievalTab.vue'
import Mem0InjectTab from '../components/intelligent-chat/Mem0InjectTab.vue'
import LLMGenerateTab from '../components/intelligent-chat/LLMGenerateTab.vue'

const activeTab = ref('document-parse')
</script>

<style scoped>
</style>

