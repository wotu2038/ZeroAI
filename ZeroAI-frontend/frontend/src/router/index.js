import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated, isAdmin } from '@/utils/auth'
import GraphView from '../views/GraphView.vue'
import EntitiesView from '../views/EntitiesView.vue'
import RelationshipsView from '../views/RelationshipsView.vue'
import ImportView from '../views/ImportView.vue'
import LLMView from '../views/LLMView.vue'
import EpisodeView from '../views/EpisodeView.vue'
import PathSearchView from '../views/PathSearchView.vue'
import RequirementsDocumentView from '../views/RequirementsDocumentView.vue'
import RequirementsQAView from '../views/RequirementsQAView.vue'
import KnowledgeManagementView from '../views/KnowledgeManagementView.vue'
import TemplateManagementView from '../views/TemplateManagementView.vue'
import TaskManagementView from '../views/TaskManagementView.vue'
import KnowledgeBaseView from '../views/KnowledgeBaseView.vue'
import KnowledgeBaseDetailView from '../views/KnowledgeBaseDetailView.vue'
import DiscoverView from '../views/DiscoverView.vue'
import DocumentLibraryView from '../views/DocumentLibraryView.vue'
import LoginView from '../views/LoginView.vue'
import UserManagementView from '../views/UserManagementView.vue'
import IntelligentChatView from '../views/IntelligentChatView.vue'

const routes = [
  {
    path: '/',
    redirect: '/graph'
  },
  {
    path: '/graph',
    name: 'graph',
    component: GraphView
  },
  {
    path: '/entities',
    name: 'entities',
    component: EntitiesView
  },
  {
    path: '/relationships',
    name: 'relationships',
    component: RelationshipsView
  },
  {
    path: '/import',
    name: 'import',
    component: ImportView
  },
  {
    path: '/llm',
    name: 'llm',
    component: LLMView
  },
  {
    path: '/episode',
    name: 'episode',
    component: EpisodeView
  },
  {
    path: '/path-search',
    name: 'path-search',
    component: PathSearchView
  },
  {
    path: '/requirements',
    redirect: '/requirements/documents'
  },
  {
    path: '/requirements/documents',
    name: 'requirements-documents',
    component: RequirementsDocumentView
  },
  {
    path: '/requirements/qa',
    name: 'requirements-qa',
    component: RequirementsQAView
  },
  {
    path: '/requirements/knowledge',
    name: 'requirements-knowledge',
    component: KnowledgeManagementView
  },
  {
    path: '/requirements/templates',
    name: 'requirements-templates',
    component: TemplateManagementView
  },
  {
    path: '/requirements/tasks',
    name: 'requirements-tasks',
    component: TaskManagementView
  },
  {
    path: '/knowledge-bases',
    name: 'knowledge-bases',
    component: KnowledgeBaseDetailView,
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge-bases/:id',
    name: 'knowledge-base-detail',
    component: KnowledgeBaseDetailView,
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge-bases-list',
    name: 'knowledge-bases-list',
    component: KnowledgeBaseView,
    meta: { requiresAuth: true }
  },
  {
    path: '/discover',
    name: 'discover',
    component: DiscoverView,
    meta: { requiresAuth: true }
  },
  {
    path: '/document-library',
    name: 'document-library',
    component: DocumentLibraryView,
    meta: { requiresAuth: true }
  },
  {
    path: '/user-management',
    name: 'user-management',
    component: UserManagementView,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/intelligent-chat',
    name: 'intelligent-chat',
    component: IntelligentChatView,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：检查登录状态
router.beforeEach((to, from, next) => {
  const isLoginPage = to.path === '/login'
  const authenticated = isAuthenticated()
  
  console.log('路由守卫:', { path: to.path, isLoginPage, authenticated })
  
  // 如果已登录用户访问登录页，跳转到首页
  if (isLoginPage && authenticated) {
    console.log('已登录用户访问登录页，跳转到首页')
    next('/knowledge-bases')
    return
  }
  
  // 如果未登录用户访问登录页，直接放行
  if (isLoginPage && !authenticated) {
    console.log('未登录用户访问登录页，放行')
    next()
    return
  }
  
  // 如果未登录，所有页面都跳转到登录页
  if (!authenticated) {
    console.log('未登录，跳转到登录页')
    next({
      path: '/login',
      query: { redirect: to.fullPath }
    })
    return
  }
  
  // 检查是否需要Admin权限
  if (to.meta?.requiresAdmin && !isAdmin()) {
    console.log('需要Admin权限，但当前用户不是Admin，跳转到首页')
    message.warning('您没有权限访问此页面')
    next('/knowledge-bases')
    return
  }
  
  // 已登录，放行
  console.log('已登录，放行')
  next()
})

export default router

