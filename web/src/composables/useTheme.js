/**
 * 主题管理 Composable
 * 支持亮色/暗色模式切换
 */
import { ref, watch, onMounted } from 'vue'

const THEME_KEY = 'gov-policy-theme'

export function useTheme() {
  const isDark = ref(false)

  // 从localStorage加载主题设置
  const loadTheme = () => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved) {
      isDark.value = saved === 'dark'
    } else {
      // 检查系统偏好
      isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    applyTheme()
  }

  // 应用主题
  const applyTheme = () => {
    if (isDark.value) {
      document.documentElement.setAttribute('data-theme', 'dark')
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.setAttribute('data-theme', 'light')
      document.documentElement.classList.remove('dark')
    }
  }

  // 切换主题
  const toggleTheme = () => {
    isDark.value = !isDark.value
    localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
    applyTheme()
  }

  // 设置主题
  const setTheme = (theme) => {
    isDark.value = theme === 'dark'
    localStorage.setItem(THEME_KEY, theme)
    applyTheme()
  }

  // 监听系统主题变化
  const watchSystemTheme = () => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', (e) => {
      if (!localStorage.getItem(THEME_KEY)) {
        isDark.value = e.matches
        applyTheme()
      }
    })
  }

  onMounted(() => {
    loadTheme()
    watchSystemTheme()
  })

  return {
    isDark,
    toggleTheme,
    setTheme
  }
}
