<template>
  <a-card title="召回结果统计" class="statistics-card">
    <a-row :gutter="16">
      <a-col :span="12">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="总召回数">
            <span class="stat-value">{{ result.total_count || 0 }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="相似需求">
            <span class="stat-value">{{ result.requirement_count || 0 }}</span>
          </a-descriptions-item>
        </a-descriptions>
      </a-col>
      <a-col :span="12">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="相似规则">
            <span class="stat-value">{{ result.rule_count || 0 }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="相似流程">
            <span class="stat-value">{{ result.flow_count || 0 }}</span>
          </a-descriptions-item>
        </a-descriptions>
      </a-col>
    </a-row>

    <!-- 来源统计 -->
    <a-divider />
    <div class="source-stats">
      <a-space size="large" wrap>
        <div class="source-stat-item">
          <span class="source-label">Graphiti:</span>
          <a-tag color="blue" class="source-count">{{ result.graphiti_count || 0 }}</a-tag>
        </div>
        <div class="source-stat-item">
          <span class="source-label">Cognee:</span>
          <a-tag color="green" class="source-count">{{ result.cognee_count || 0 }}</a-tag>
        </div>
        <div class="source-stat-item">
          <span class="source-label">Milvus:</span>
          <a-tag color="purple" class="source-count">{{ result.milvus_count || 0 }}</a-tag>
        </div>
      </a-space>
    </div>

    <!-- 向量类型统计 -->
    <a-divider />
    <div class="type-stats">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="Entity">
              <span class="stat-value">{{ result.entity_count || 0 }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="Episode">
              <span class="stat-value">{{ result.episode_count || 0 }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="Section">
              <span class="stat-value">{{ result.section_count || 0 }}</span>
            </a-descriptions-item>
          </a-descriptions>
        </a-col>
        <a-col :span="12">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="Edge">
              <span class="stat-value">{{ result.edge_count || 0 }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="Community">
              <span class="stat-value">{{ result.community_count || 0 }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="Image">
              <a-tag color="blue" class="stat-value">{{ result.image_count || 0 }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="Table">
              <a-tag color="green" class="stat-value">{{ result.table_count || 0 }}</a-tag>
            </a-descriptions-item>
          </a-descriptions>
        </a-col>
      </a-row>
    </div>
  </a-card>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.statistics-card {
  margin-bottom: 24px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1890ff;
}

.source-stats {
  margin-top: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.source-stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-label {
  font-weight: 500;
  color: #666;
}

.type-stats {
  margin-top: 16px;
}

.type-stats .stat-value {
  font-size: 14px;
  font-weight: 600;
}

.source-count {
  font-size: 14px;
  font-weight: 600;
}
</style>

