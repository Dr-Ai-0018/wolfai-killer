export function showTimedToast(toast, message, type = 'info', duration = 3000) {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => {
    toast.show = false
  }, duration)
}

export function formatTokenExpiry(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function normalizeAdminConfig(data) {
  return {
    ...data,
    model_ids: data.model_ids || data.models || [],
  }
}

export function resolveApiRequestConfig(config, currentConfig) {
  return {
    apiUrl: config.apiUrl || currentConfig.api_url,
    apiKey: config.apiKey || 'use_existing',
  }
}

export function mergeSelectedModels(existingModelIds, selectedModels) {
  const existingModels = new Set(existingModelIds || [])
  const newModels = selectedModels.filter((model) => !existingModels.has(model))
  return {
    merged: [...(existingModelIds || []), ...newModels],
    added: newModels,
  }
}
