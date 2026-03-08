const RAW_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002/api'

const normalizeApiUrl = (value) => {
  const trimmed = String(value || '').trim().replace(/\/+$/, '')
  if (!trimmed) {
    return 'http://localhost:5002/api'
  }

  if (trimmed.endsWith('/api')) {
    return trimmed
  }

  return `${trimmed}/api`
}

export const API_URL = normalizeApiUrl(RAW_API_URL)
