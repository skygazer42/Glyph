/**
 * 共享全局主题；每个消费者只负责自己的系统主题监听。
 */
import { ref, onMounted, onUnmounted } from 'vue'

const THEME_KEY = 'gov-policy-theme'
const isDark = ref(false)
let isInitialized = false

export function useTheme() {
  let mediaQuery = null

  const readSavedTheme = () => {
    try {
      return localStorage.getItem(THEME_KEY)
    } catch (error) {
      console.warn('无法读取主题设置:', error)
      return null
    }
  }

  const applyTheme = () => {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  const setTheme = (theme) => {
    isDark.value = theme === 'dark'
    applyTheme()
    try {
      localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
    } catch (error) {
      console.warn('无法保存主题设置:', error)
    }
  }

  const toggleTheme = () => setTheme(isDark.value ? 'light' : 'dark')

  const handleSystemThemeChange = (event) => {
    const saved = readSavedTheme()
    if (saved !== 'dark' && saved !== 'light') {
      isDark.value = event.matches
      applyTheme()
    }
  }

  onMounted(() => {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    if (!isInitialized) {
      const saved = readSavedTheme()
      isDark.value = saved === 'dark' || (saved !== 'light' && mediaQuery.matches)
      isInitialized = true
      applyTheme()
    }
    mediaQuery.addEventListener('change', handleSystemThemeChange)
  })

  onUnmounted(() => {
    mediaQuery?.removeEventListener('change', handleSystemThemeChange)
  })

  return { isDark, toggleTheme, setTheme }
}
