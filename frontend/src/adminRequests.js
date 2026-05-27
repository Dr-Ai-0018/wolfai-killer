import { normalizeAdminConfig, resolveApiRequestConfig } from '@/adminPanel'

export function isUnauthorizedError(error) {
  return error?.response?.status === 401
}

export function getErrorMessage(error, fallback = '操作失败') {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}

export async function verifyAdminSession(api) {
  if (!api.isTokenValid()) {
    return { authenticated: false, tokenExpiry: null }
  }

  await api.verify()
  return {
    authenticated: true,
    tokenExpiry: localStorage.getItem('werewolf_admin_token_expiry'),
  }
}

export async function fetchAdminConfig(api) {
  const res = await api.getConfig()
  return {
    currentConfig: normalizeAdminConfig(res.data),
    apiUrl: res.data.api_url || '',
  }
}

export async function loginAdmin(api, password) {
  const res = await api.login(password)
  return {
    success: !!res.data.success,
    tokenExpiry: res.data.expires_at || null,
  }
}

export async function updateAdminApiConfig(api, config) {
  const updates = {}
  if (config.apiUrl) updates.api_url = config.apiUrl
  if (config.apiKey) updates.api_key = config.apiKey
  await api.updateConfig(updates)
}

export async function requestRemoteModels(api, config, currentConfig) {
  const { apiUrl, apiKey } = resolveApiRequestConfig(config, currentConfig)
  if (!apiUrl) {
    return { missingApiUrl: true, models: [], total: 0, success: false, message: '请先配置API地址' }
  }

  const res = await api.fetchModels(apiUrl, apiKey)
  return {
    missingApiUrl: false,
    success: !!res.data.success,
    message: res.data.message || '',
    models: res.data.model_ids || res.data.models || [],
    total: Number(res.data.total || 0),
  }
}

export async function updateAdminModels(api, modelIds) {
  await api.updateConfig({ model_ids: modelIds })
}
