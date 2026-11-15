import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import App from './App.vue'
import './styles/global.css'

const app = createApp(App)

// 注册所有图标
for (const [iconName, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(iconName, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
