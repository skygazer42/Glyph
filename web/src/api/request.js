import axios from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

// 创建 axios 实例
const instance = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
instance.interceptors.request.use(
  config => {
    // 可以在这里添加 token
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  error => {
    console.error('Request Error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
instance.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    // 错误处理
    let message = '请求失败'
    let description = ''

    if (error.response) {
      // 服务器响应错误
      const { status, data } = error.response

      switch (status) {
        case 400:
          message = '请求参数错误'
          description = data.message || data.detail || '请检查输入参数'
          break
        case 401:
          message = '未授权'
          description = '请重新登录'
          break
        case 403:
          message = '拒绝访问'
          description = '您没有权限执行此操作'
          break
        case 404:
          message = '资源不存在'
          description = '请求的资源未找到'
          break
        case 500:
          message = '服务器错误'
          description = data.message || data.detail || '服务器内部错误，请稍后重试'
          break
        case 502:
          message = '网关错误'
          description = '服务暂时不可用'
          break
        case 503:
          message = '服务不可用'
          description = '服务器正在维护，请稍后重试'
          break
        default:
          message = `请求失败 (${status})`
          description = data.message || data.detail || error.message
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      message = '网络错误'
      description = '无法连接到服务器，请检查网络连接'
    } else {
      // 请求配置错误
      message = '请求配置错误'
      description = error.message
    }

    // 显示错误通知
    if (error.config?.hideErrorMessage !== true) {
      if (description) {
        ElNotification({
          title: message,
          message: description,
          type: 'error',
          duration: 5000,
          position: 'top-right'
        })
      } else {
        ElMessage.error(message)
      }
    }

    console.error('API Error:', error)

    // 创建统一的错误对象
    const apiError = {
      message,
      description,
      status: error.response?.status,
      data: error.response?.data,
      originalError: error
    }

    return Promise.reject(apiError)
  }
)

// 导出实例
export default instance

// 导出请求方法（支持配置是否隐藏错误提示）
export const request = {
  get: (url, config = {}) => instance.get(url, config),
  post: (url, data, config = {}) => instance.post(url, data, config),
  put: (url, data, config = {}) => instance.put(url, data, config),
  delete: (url, config = {}) => instance.delete(url, config),
  patch: (url, data, config = {}) => instance.patch(url, data, config)
}
