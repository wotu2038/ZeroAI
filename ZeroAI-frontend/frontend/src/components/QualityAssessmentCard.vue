<template>
  <a-card title="质量评估报告" size="small" :bordered="false">
    <!-- 综合评分 -->
    <div class="overall-score">
      <a-progress
        type="dashboard"
        :percent="overallScore"
        :stroke-color="overallScoreColor"
        :width="120"
      >
        <template #format>
          <div class="score-content">
            <span class="score-value">{{ overallScore }}</span>
            <span class="score-label">综合评分</span>
          </div>
        </template>
      </a-progress>
      <div class="score-stars">
        <StarFilled v-for="i in filledStars" :key="'filled-'+i" style="color: #fadb14" />
        <StarOutlined v-for="i in emptyStars" :key="'empty-'+i" style="color: #d9d9d9" />
      </div>
    </div>
    
    <!-- 分项评分 -->
    <div class="score-items">
      <div class="score-item">
        <div class="score-item-header">
          <span class="score-item-label">
            <BlockOutlined style="margin-right: 4px" />
            分块质量
          </span>
          <span class="score-item-value" :style="{ color: getScoreColor(chunkingScore) }">
            {{ chunkingScore }}%
          </span>
        </div>
        <a-progress
          :percent="chunkingScore"
          :stroke-color="getScoreColor(chunkingScore)"
          :show-info="false"
          size="small"
        />
        <div class="score-item-desc" v-if="quality.chunking_details">
          {{ quality.chunking_details }}
        </div>
      </div>
      
      <div class="score-item">
        <div class="score-item-header">
          <span class="score-item-label">
            <ApartmentOutlined style="margin-right: 4px" />
            提取质量
          </span>
          <span class="score-item-value" :style="{ color: getScoreColor(extractionScore) }">
            {{ extractionScore }}%
          </span>
        </div>
        <a-progress
          :percent="extractionScore"
          :stroke-color="getScoreColor(extractionScore)"
          :show-info="false"
          size="small"
        />
        <div class="score-item-desc" v-if="quality.extraction_details">
          {{ quality.extraction_details }}
        </div>
      </div>
      
      <div class="score-item">
        <div class="score-item-header">
          <span class="score-item-label">
            <DeploymentUnitOutlined style="margin-right: 4px" />
            图谱结构
          </span>
          <span class="score-item-value" :style="{ color: getScoreColor(graphScore) }">
            {{ graphScore }}%
          </span>
        </div>
        <a-progress
          :percent="graphScore"
          :stroke-color="getScoreColor(graphScore)"
          :show-info="false"
          size="small"
        />
        <div class="score-item-desc" v-if="quality.graph_details">
          {{ quality.graph_details }}
        </div>
      </div>
    </div>
    
    <!-- 知识图谱概览 -->
    <a-divider style="margin: 16px 0 12px 0">知识图谱概览</a-divider>
    
    <a-row :gutter="[16, 8]">
      <a-col :span="8">
        <a-statistic
          title="实体数"
          :value="statistics.entity_count || 0"
          :value-style="{ fontSize: '20px' }"
        >
          <template #prefix>
            <NodeIndexOutlined />
          </template>
        </a-statistic>
      </a-col>
      <a-col :span="8">
        <a-statistic
          title="关系数"
          :value="statistics.edge_count || 0"
          :value-style="{ fontSize: '20px' }"
        >
          <template #prefix>
            <ShareAltOutlined />
          </template>
        </a-statistic>
      </a-col>
      <a-col :span="8">
        <a-statistic
          title="社区数"
          :value="statistics.community_count || 0"
          :value-style="{ fontSize: '20px' }"
        >
          <template #prefix>
            <ClusterOutlined />
          </template>
        </a-statistic>
      </a-col>
    </a-row>
    
    <!-- 状态标签 -->
    <div class="quality-status" v-if="quality.status">
      <a-tag v-if="quality.status === 'passed'" color="success">
        <CheckCircleOutlined /> 质量达标
      </a-tag>
      <a-tag v-else-if="quality.status === 'pending_review'" color="warning">
        <ExclamationCircleOutlined /> 待人工审核
      </a-tag>
      <a-tag v-else-if="quality.status === 'retrying'" color="processing">
        <SyncOutlined spin /> 正在重试
      </a-tag>
      <a-tag v-else-if="quality.status === 'failed'" color="error">
        <CloseCircleOutlined /> 质量不达标
      </a-tag>
    </div>
    
    <!-- 建议 -->
    <div v-if="quality.suggestions && quality.suggestions.length > 0" class="quality-suggestions">
      <a-divider style="margin: 12px 0 8px 0">改进建议</a-divider>
      <ul style="margin: 0; padding-left: 16px">
        <li v-for="(suggestion, index) in quality.suggestions" :key="index" style="color: #666; font-size: 12px">
          {{ suggestion }}
        </li>
      </ul>
    </div>
  </a-card>
</template>

<script setup>
import { computed } from 'vue'
import {
  StarFilled,
  StarOutlined,
  BlockOutlined,
  ApartmentOutlined,
  DeploymentUnitOutlined,
  NodeIndexOutlined,
  ShareAltOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined
} from '@ant-design/icons-vue'

const props = defineProps({
  quality: {
    type: Object,
    default: () => ({})
  },
  statistics: {
    type: Object,
    default: () => ({})
  }
})

// 计算分数
const chunkingScore = computed(() => props.quality.chunking_score || 0)
const extractionScore = computed(() => props.quality.extraction_score || 0)
const graphScore = computed(() => props.quality.graph_score || 0)

const overallScore = computed(() => {
  if (props.quality.overall_score !== undefined) {
    return props.quality.overall_score
  }
  // 计算加权平均分
  return Math.round((chunkingScore.value * 0.25 + extractionScore.value * 0.4 + graphScore.value * 0.35))
})

// 星级评分
const filledStars = computed(() => {
  if (overallScore.value >= 90) return 5
  if (overallScore.value >= 80) return 4
  if (overallScore.value >= 70) return 3
  if (overallScore.value >= 60) return 2
  return 1
})

const emptyStars = computed(() => 5 - filledStars.value)

// 颜色
const overallScoreColor = computed(() => getScoreColor(overallScore.value))

const getScoreColor = (score) => {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#ff4d4f'
}
</script>

<style scoped>
.overall-score {
  text-align: center;
  margin-bottom: 24px;
}

.score-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.score-value {
  font-size: 28px;
  font-weight: bold;
  color: #1890ff;
}

.score-label {
  font-size: 12px;
  color: #999;
}

.score-stars {
  margin-top: 8px;
  font-size: 16px;
}

.score-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-item {
  background: #fafafa;
  padding: 12px;
  border-radius: 6px;
}

.score-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.score-item-label {
  font-size: 13px;
  color: #333;
}

.score-item-value {
  font-weight: 600;
}

.score-item-desc {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.quality-status {
  margin-top: 16px;
  text-align: center;
}

.quality-suggestions {
  margin-top: 8px;
}
</style>

