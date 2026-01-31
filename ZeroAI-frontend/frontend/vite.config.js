import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3008,
    proxy: {
      '/api': {
        // 开发环境代理配置
        // 如果设置了 VITE_API_BASE_URL 环境变量，可以使用该值
        // 否则默认代理到 localhost:8000
        target: process.env.VITE_API_BASE_URL?.replace('/api', '') || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})

