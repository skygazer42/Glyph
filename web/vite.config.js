import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'GLYPH_')
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '0.0.0.0', // 允许外网访问
      port: 3000,
      proxy: {
        '/api': {
          target: environment.GLYPH_API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true
        }
      }
    }
  }
})
