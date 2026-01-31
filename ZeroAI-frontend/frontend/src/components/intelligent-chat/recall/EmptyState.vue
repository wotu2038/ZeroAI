<template>
  <a-empty
    description="请输入查询文本并点击执行按钮"
    :image="Empty.PRESENTED_IMAGE_SIMPLE"
    class="empty-state"
  />
</template>

<script setup>
import { Empty } from 'ant-design-vue'
</script>

<style scoped>
.empty-state {
  margin: 80px 0;
}
</style>

