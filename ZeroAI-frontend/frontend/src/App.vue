<template>
  <a-config-provider :locale="locale">
    <!-- 登录页面不显示布局 -->
    <router-view v-if="$route.path === '/login'" />
    <!-- 其他页面显示完整布局 -->
    <a-layout v-else style="min-height: 100vh">
      <a-layout-header style="background: #001529; padding: 0 24px; display: flex; justify-content: space-between; align-items: center">
        <div style="color: white; font-size: 20px; font-weight: bold">
          ZeroAI - 知识图谱应用
        </div>
        <div v-if="currentUser" style="display: flex; align-items: center; gap: 16px; color: white">
          <span>{{ currentUser.username }}</span>
          <a-button type="text" size="small" @click="handleLogout" style="color: white">
            退出
          </a-button>
        </div>
      </a-layout-header>
      <a-layout>
        <a-layout-sider width="200" style="background: #fff">
          <a-menu
            v-model:selectedKeys="selectedKeys"
            v-model:openKeys="openKeys"
            mode="inline"
            :style="{ height: '100%', borderRight: 0 }"
            @click="handleMenuClick"
          >
            <!-- 关系助手菜单已注释 -->
            <!--
            <a-sub-menu key="relationship-assistant">
              <template #icon><ShareAltOutlined /></template>
              <template #title>关系助手</template>
            <a-menu-item key="graph">
              <template #icon><NodeIndexOutlined /></template>
              知识图谱
            </a-menu-item>
            <a-menu-item key="entities">
              <template #icon><DatabaseOutlined /></template>
              实体管理
            </a-menu-item>
            <a-menu-item key="relationships">
              <template #icon><ShareAltOutlined /></template>
              关系管理
            </a-menu-item>
            <a-menu-item key="import">
              <template #icon><UploadOutlined /></template>
              数据导入
            </a-menu-item>
            <a-menu-item key="llm">
              <template #icon><RobotOutlined /></template>
              智能对话
            </a-menu-item>
            <a-menu-item key="episode">
              <template #icon><FileAddOutlined /></template>
              添加 Episode
            </a-menu-item>
            <a-menu-item key="path-search">
              <template #icon><SearchOutlined /></template>
              查关系
            </a-menu-item>
            </a-sub-menu>
            -->
            <!-- 需求助手 -->
            <a-sub-menu key="requirements">
              <template #icon><FileTextOutlined /></template>
              <template #title>需求助手</template>
              <a-menu-item key="knowledge-bases">
                知识库
              </a-menu-item>
              <a-menu-item key="document-library">
                文档库
              </a-menu-item>
              <a-menu-item key="discover">
                发现
              </a-menu-item>
            </a-sub-menu>
            
            <!-- 后台管理 -->
            <a-sub-menu v-if="canAccessBackendManagement()" key="backend-management">
              <template #icon><DatabaseOutlined /></template>
              <template #title>后台管理</template>
              <a-menu-item key="intelligent-chat">
                智能对话
              </a-menu-item>
              <a-menu-item key="requirements-qa">
                智能问答
              </a-menu-item>
              <a-menu-item key="requirements-documents">
                文档管理
              </a-menu-item>
              <a-menu-item key="requirements-knowledge">
                知识管理
              </a-menu-item>
              <a-menu-item key="requirements-templates">
                模板管理
              </a-menu-item>
              <a-menu-item key="requirements-tasks">
                任务管理
              </a-menu-item>
              <a-menu-item v-if="canAccessUserManagement()" key="user-management">
                用户管理
              </a-menu-item>
            </a-sub-menu>
          </a-menu>
        </a-layout-sider>
        <a-layout-content style="padding: 24px; background: #f0f2f5">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import {
  NodeIndexOutlined,
  DatabaseOutlined,
  ShareAltOutlined,
  UploadOutlined,
  RobotOutlined,
  FileAddOutlined,
  SearchOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import { getUser, removeToken, isAdmin } from '@/utils/auth'

// 判断是否可以访问后台管理
const canAccessBackendManagement = () => {
  const user = getUser()
  if (!user) return false
  // Admin 和 Manage 角色可以访问后台管理
  return user.role === 'admin' || user.role === 'manage'
}

// 判断是否可以访问用户管理
const canAccessUserManagement = () => {
  const user = getUser()
  if (!user) return false
  // 只有 Admin 角色可以访问用户管理
  return user.role === 'admin'
}

const locale = zhCN
const router = useRouter()
const route = useRoute()
const selectedKeys = ref([route.name || 'graph'])
const openKeys = ref([])
const currentUser = ref(getUser())

// 根据当前路由设置 openKeys
const updateOpenKeys = (routeName) => {
  const keys = []
  
  // 关系助手下的菜单项（已注释）
  // const relationshipAssistantRoutes = ['graph', 'entities', 'relationships', 'import', 'llm', 'episode', 'path-search']
  // if (relationshipAssistantRoutes.includes(routeName)) {
  //   keys.push('relationship-assistant')
  // }
  
  // 需求助手下的菜单项
  if (routeName && (routeName === 'knowledge-bases' || routeName === 'document-library' || routeName === 'discover')) {
    keys.push('requirements')
  }
  
  // 后台管理下的菜单项
  if (routeName && (routeName.startsWith('requirements') || routeName === 'user-management' || routeName === 'intelligent-chat')) {
    keys.push('backend-management')
  }
  
  openKeys.value = keys
}

watch(() => route.name, (newName) => {
  selectedKeys.value = [newName]
  updateOpenKeys(newName)
}, { immediate: true })

const handleMenuClick = ({ key }) => {
  router.push({ name: key })
}

// 退出登录
const handleLogout = () => {
  removeToken()
  currentUser.value = null
  message.success('已退出登录')
  router.push('/login')
}

// 监听路由变化，更新用户信息
watch(() => route.path, () => {
  currentUser.value = getUser()
}, { immediate: true })

// 组件挂载时获取用户信息
onMounted(() => {
  currentUser.value = getUser()
})
</script>

<style>
#app {
  width: 100%;
  height: 100%;
}
</style>

