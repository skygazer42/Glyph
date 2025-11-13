import axios from 'axios'
import { ElMessage } from 'element-plus'

const instance = axios.create({
  baseURL: '/api',
  timeout: 120000, // 增加到120秒,适配LightRAG较慢的查询
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：添加重试配置
instance.interceptors.request.use(
  config => {
    // 为每个请求添加重试配置（如果没有的话）
    if (!config.retryConfig) {
      config.retryConfig = {
        retries: 3, // 最多重试3次
        retryDelay: 1000, // 初始延迟1秒
        retryCondition: (error) => {
          // 只对网络错误和5xx错误重试
          return !error.response || (error.response.status >= 500 && error.response.status < 600)
        }
      }
    }
    config.__retryCount = config.__retryCount || 0
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器：处理错误和重试
instance.interceptors.response.use(
  response => response.data,
  async error => {
    const config = error.config

    // 如果没有配置或不应该重试，直接拒绝
    if (!config || !config.retryConfig) {
      handleError(error)
      return Promise.reject(error)
    }

    const { retries, retryDelay, retryCondition } = config.retryConfig

    // 检查是否应该重试
    const shouldRetry = retryCondition(error)
    const hasRetriesLeft = config.__retryCount < retries

    if (shouldRetry && hasRetriesLeft) {
      config.__retryCount += 1

      // 计算延迟时间（指数退避）
      const delay = retryDelay * Math.pow(2, config.__retryCount - 1)

      console.log(
        `Retrying request (${config.__retryCount}/${retries}) after ${delay}ms:`,
        config.url
      )

      // 等待后重试
      await new Promise(resolve => setTimeout(resolve, delay))

      return instance(config)
    }

    // 重试次数用尽或不应重试
    handleError(error, config.__retryCount)
    return Promise.reject(error)
  }
)

/**
 * 统一错误处理
 */
function handleError(error, retryCount = 0) {
  const retryInfo = retryCount > 0 ? ` (重试${retryCount}次后仍失败)` : ''

  if (error.response) {
    // 服务器返回错误状态码
    const status = error.response.status
    const message = error.response.data?.message || error.response.data?.detail || '请求失败'

    switch (status) {
      case 400:
        ElMessage.error(`请求参数错误: ${message}`)
        break
      case 401:
        ElMessage.error('未授权，请重新登录')
        break
      case 403:
        ElMessage.error('拒绝访问')
        break
      case 404:
        ElMessage.error('请求的资源不存在')
        break
      case 500:
        ElMessage.error(`服务器错误${retryInfo}: ${message}`)
        break
      case 502:
      case 503:
      case 504:
        ElMessage.error(`服务暂时不可用${retryInfo}，请稍后重试`)
        break
      default:
        ElMessage.error(`请求失败${retryInfo}: ${message}`)
    }
  } else if (error.request) {
    // 请求已发出但没有收到响应（网络错误）
    console.error('Network Error:', error.request)
    ElMessage.error(`网络连接失败${retryInfo}，请检查网络设置`)
  } else {
    // 其他错误
    console.error('Error:', error.message)
    ElMessage.error(`请求配置错误: ${error.message}`)
  }
}

/**
 * 为特定请求禁用重试
 */
export function withoutRetry(config) {
  return {
    ...config,
    retryConfig: {
      retries: 0,
      retryCondition: () => false
    }
  }
}

/**
 * 自定义重试配置
 */
export function withRetryConfig(config, retryConfig) {
  return {
    ...config,
    retryConfig: {
      retries: retryConfig.retries || 3,
      retryDelay: retryConfig.retryDelay || 1000,
      retryCondition: retryConfig.retryCondition || ((error) => {
        return !error.response || (error.response.status >= 500 && error.response.status < 600)
      })
    }
  }
}

export default instance
