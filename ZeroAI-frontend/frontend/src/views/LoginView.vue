<template>
  <div class="login-container">
    <a-card class="login-card" :bordered="false">
      <template #title>
        <div style="text-align: center; font-size: 24px; font-weight: bold">
          ZeroAI - 知识图谱应用
        </div>
      </template>
      
      <a-tabs v-model:activeKey="activeTab" centered>
        <a-tab-pane key="login" tab="登录">
          <a-form
            :model="loginForm"
            :rules="loginRules"
            @finish="handleLogin"
            :label-col="{ span: 6 }"
            :wrapper-col="{ span: 18 }"
          >
            <a-form-item label="用户名" name="username">
              <a-input v-model:value="loginForm.username" placeholder="请输入用户名" />
            </a-form-item>
            <a-form-item label="密码" name="password">
              <a-input-password v-model:value="loginForm.password" placeholder="请输入密码" />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6, span: 18 }">
              <a-button type="primary" html-type="submit" :loading="loading" block>
                登录
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="register" tab="注册">
          <a-form
            :model="registerForm"
            :rules="registerRules"
            @finish="handleRegister"
            :label-col="{ span: 6 }"
            :wrapper-col="{ span: 18 }"
          >
            <a-form-item label="用户名" name="username">
              <a-input v-model:value="registerForm.username" placeholder="请输入用户名" />
            </a-form-item>
            <a-form-item label="邮箱" name="email">
              <a-input v-model:value="registerForm.email" placeholder="请输入邮箱（可选）" />
            </a-form-item>
            <a-form-item label="密码" name="password">
              <a-input-password v-model:value="registerForm.password" placeholder="请输入密码" />
            </a-form-item>
            <a-form-item label="确认密码" name="confirmPassword">
              <a-input-password v-model:value="registerForm.confirmPassword" placeholder="请再次输入密码" />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6, span: 18 }">
              <a-button type="primary" html-type="submit" :loading="loading" block>
                注册
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { login, register } from '@/api/auth'
import { setToken, setUser } from '@/utils/auth'

const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

// 登录验证规则
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 注册验证规则
const validateConfirmPassword = (rule, value) => {
  if (!value) {
    return Promise.reject('请再次输入密码')
  }
  if (value !== registerForm.password) {
    return Promise.reject('两次输入的密码不一致')
  }
  return Promise.resolve()
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度为3-50个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 72, message: '密码长度为6-72个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 登录
const handleLogin = async () => {
  loading.value = true
  try {
    const res = await login({
      username: loginForm.username,
      password: loginForm.password
    })
    
    // 保存Token和用户信息
    setToken(res.access_token)
    setUser(res.user)
    
    message.success('登录成功')
    
    // 等待一下确保Token已保存
    await new Promise(resolve => setTimeout(resolve, 100))
    
    // 跳转到首页或之前访问的页面
    const redirect = router.currentRoute.value.query.redirect || '/knowledge-bases'
    router.push(redirect)
  } catch (error) {
    message.error('登录失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 注册
const handleRegister = async () => {
  loading.value = true
  try {
    const data = {
      username: registerForm.username,
      password: registerForm.password
    }
    if (registerForm.email) {
      data.email = registerForm.email
    }
    
    const res = await register(data)
    
    // 保存Token和用户信息
    setToken(res.access_token)
    setUser(res.user)
    
    message.success('注册成功')
    
    // 等待一下确保Token已保存
    await new Promise(resolve => setTimeout(resolve, 100))
    
    // 跳转到知识库页面
    router.push('/knowledge-bases')
  } catch (error) {
    message.error('注册失败: ' + error.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 450px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>

