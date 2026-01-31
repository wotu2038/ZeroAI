<template>
  <a-card title="数据导入">
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="csv" tab="CSV导入">
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="CSV格式说明">
            <a-typography-paragraph>
              <pre>{{ csvFormat }}</pre>
            </a-typography-paragraph>
          </a-form-item>
          <a-form-item label="CSV数据">
            <a-textarea
              v-model:value="csvData"
              :rows="10"
              placeholder="粘贴CSV数据..."
            />
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 4, span: 20 }">
            <a-button type="primary" @click="handleImportCSV" :loading="importing">
              导入CSV
            </a-button>
          </a-form-item>
        </a-form>
      </a-tab-pane>

      <a-tab-pane key="json" tab="JSON导入">
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="JSON格式说明">
            <a-typography-paragraph>
              <pre>{{ jsonFormat }}</pre>
            </a-typography-paragraph>
          </a-form-item>
          <a-form-item label="JSON数据">
            <a-textarea
              v-model:value="jsonData"
              :rows="10"
              placeholder="粘贴JSON数据..."
            />
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 4, span: 20 }">
            <a-button type="primary" @click="handleImportJSON" :loading="importing">
              导入JSON
            </a-button>
          </a-form-item>
        </a-form>
      </a-tab-pane>

      <a-tab-pane key="llm" tab="LLM提取">
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="LLM提供商">
            <a-select v-model:value="llmProvider" style="width: 200px">
              <a-select-option value="qianwen">千问</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="文本内容">
            <a-textarea
              v-model:value="extractText"
              :rows="10"
              placeholder="输入要提取实体和关系的文本..."
            />
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 4, span: 20 }">
            <a-button type="primary" @click="handleExtract" :loading="extracting">
              提取并导入
            </a-button>
          </a-form-item>
        </a-form>
      </a-tab-pane>
    </a-tabs>

    <!-- 导入结果 -->
    <a-modal
      v-model:open="resultVisible"
      title="导入结果"
      :footer="null"
    >
      <a-descriptions :column="1">
        <a-descriptions-item label="状态">
          <a-tag :color="importResult.success ? 'success' : 'error'">
            {{ importResult.success ? '成功' : '失败' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建实体数">
          {{ importResult.entities_created }}
        </a-descriptions-item>
        <a-descriptions-item label="创建关系数">
          {{ importResult.relationships_created }}
        </a-descriptions-item>
        <a-descriptions-item label="错误信息" v-if="importResult.errors?.length">
          <ul>
            <li v-for="(error, index) in importResult.errors" :key="index">{{ error }}</li>
          </ul>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </a-card>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { importData } from '../api/import'
import { extractEntities } from '../api/llm'

const activeTab = ref('csv')
const csvData = ref('')
const jsonData = ref('')
const importing = ref(false)
const extracting = ref(false)
const llmProvider = ref('qianwen')
const extractText = ref('')
const resultVisible = ref(false)
const importResult = ref({
  success: false,
  entities_created: 0,
  relationships_created: 0,
  errors: []
})

const csvFormat = `实体导入格式：
type,name,properties
Person,张三,"{\"age\":30,\"city\":\"北京\"}"
Organization,阿里巴巴,"{\"founded\":1999}"

关系导入格式：
source,target,rel_type,rel_properties
张三,阿里巴巴,WORKS_FOR,"{\"since\":2020}"`

const jsonFormat = `{
  "entities": [
    {
      "name": "张三",
      "type": "Person",
      "properties": {"age": 30, "city": "北京"}
    }
  ],
  "relationships": [
    {
      "source": "张三",
      "target": "阿里巴巴",
      "type": "WORKS_FOR",
      "properties": {"since": 2020}
    }
  ]
}`

const handleImportCSV = async () => {
  if (!csvData.value.trim()) {
    message.warning('请输入CSV数据')
    return
  }

  importing.value = true
  try {
    const result = await importData({
      format: 'csv',
      data: csvData.value
    })
    importResult.value = result
    resultVisible.value = true
    if (result.success) {
      message.success(`导入成功！创建了 ${result.entities_created} 个实体和 ${result.relationships_created} 个关系`)
      csvData.value = ''
    } else {
      message.warning('导入完成，但有部分错误')
    }
  } catch (error) {
    message.error('导入失败: ' + error.message)
  } finally {
    importing.value = false
  }
}

const handleImportJSON = async () => {
  if (!jsonData.value.trim()) {
    message.warning('请输入JSON数据')
    return
  }

  importing.value = true
  try {
    const result = await importData({
      format: 'json',
      data: jsonData.value
    })
    importResult.value = result
    resultVisible.value = true
    if (result.success) {
      message.success(`导入成功！创建了 ${result.entities_created} 个实体和 ${result.relationships_created} 个关系`)
      jsonData.value = ''
    } else {
      message.warning('导入完成，但有部分错误')
    }
  } catch (error) {
    message.error('导入失败: ' + error.message)
  } finally {
    importing.value = false
  }
}

const handleExtract = async () => {
  if (!extractText.value.trim()) {
    message.warning('请输入要提取的文本')
    return
  }

  extracting.value = true
  try {
    const result = await extractEntities({
      provider: llmProvider.value,
      text: extractText.value
    })
    importResult.value = {
      success: true,
      entities_created: result.entities_created,
      relationships_created: result.relationships_created,
      errors: result.errors
    }
    resultVisible.value = true
    message.success(`提取完成！创建了 ${result.entities_created} 个实体和 ${result.relationships_created} 个关系`)
    extractText.value = ''
  } catch (error) {
    message.error('提取失败: ' + error.message)
  } finally {
    extracting.value = false
  }
}
</script>

