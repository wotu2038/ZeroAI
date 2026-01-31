<template>
  <a-card>
    <template #title>
      <span>需求助手</span>
    </template>
    <a-row :gutter="24">
      <a-col :span="12">
        <a-card hoverable @click="goToDocumentManagement" style="cursor: pointer; text-align: center; height: 200px">
          <template #cover>
            <div style="padding: 40px 20px">
              <FileTextOutlined style="font-size: 48px; color: #1890ff" />
            </div>
          </template>
          <a-card-meta title="文档管理" description="管理需求文档，查找相似需求，生成新文档" />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card hoverable @click="goToSmartQA" style="cursor: pointer; text-align: center; height: 200px">
          <template #cover>
            <div style="padding: 40px 20px">
              <QuestionCircleOutlined style="font-size: 48px; color: #52c41a" />
            </div>
          </template>
          <a-card-meta title="智能问答" description="基于需求文档进行智能问答" />
        </a-card>
      </a-col>
    </a-row>
  </a-card>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { FileTextOutlined, QuestionCircleOutlined } from '@ant-design/icons-vue'

const router = useRouter()

const goToDocumentManagement = () => {
  router.push({ name: 'requirements-documents' })
}

const goToSmartQA = () => {
  router.push({ name: 'requirements-qa' })
}
</script>

<style scoped>
</style>
