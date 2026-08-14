const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/auth';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res;
}

export const api = {
  // Auth
  register: (data: { email: string; password: string; display_name: string }) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),
  login: (data: { email: string; password: string }) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),

  // User
  onboarding: (data: { role: string; interest_tags: string[] }) =>
    request('/users/onboarding', { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),
  getMe: () => request('/users/me').then(r => r.json()),
  updateMe: (data: any) => request('/users/me', { method: 'PUT', body: JSON.stringify(data) }).then(r => r.json()),

  // Feed
  getStats: () => request('/feed/stats').then(r => r.json()),
  getDailyStats: (days = 30) => request(`/feed/stats/daily?days=${days}`).then(r => r.json()),
  getDigest: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(`/feed/digest${qs}`).then(r => r.json());
  },
  getDailyBriefing: () => fetch(`${API_BASE}/feed/daily-briefing`).then(r => r.json()),
  getDailyInsight: () => fetch(`${API_BASE}/feed/daily-insight`).then(r => r.json()),
  getFeed: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(`/feed${qs}`).then(r => r.json());
  },
  getKeywords: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(`/feed/keywords${qs}`).then(r => r.json());
  },
  getArticle: (id: string) => request(`/article/${id}`).then(r => r.json()),
  recordAction: (id: string, action: string) =>
    request(`/article/${id}/action?action=${action}`, { method: 'POST' }).then(r => r.json()),
  search: (params: Record<string, string>) =>
    request('/search?' + new URLSearchParams(params).toString()).then(r => r.json()),

  // Bookmarks
  getBookmarks: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(`/bookmarks${qs}`).then(r => r.json());
  },
  addBookmark: (id: string) => request(`/bookmarks/${id}`, { method: 'POST' }).then(r => r.json()),
  removeBookmark: (id: string) => request(`/bookmarks/${id}`, { method: 'DELETE' }).then(r => r.json()),

  // Notebooks
  getNotebooks: () => request('/notebooks').then(r => r.json()),
  createNotebook: (data: { title: string; description?: string }) =>
    request('/notebooks', { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),
  getNotebook: (id: string) => request(`/notebooks/${id}`).then(r => r.json()),
  deleteNotebook: (id: string) => request(`/notebooks/${id}`, { method: 'DELETE' }).then(r => r.json()),
  addArticlesToNotebook: (id: string, articleIds: string[]) =>
    request(`/notebooks/${id}/articles`, { method: 'POST', body: JSON.stringify({ article_ids: articleIds }) }).then(r => r.json()),
  addDocumentToNotebook: (id: string, data: { type: string; content?: string; url?: string }) =>
    request(`/notebooks/${id}/documents`, { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),
  deleteNotebookItem: (nbId: string, itemId: string) =>
    request(`/notebooks/${nbId}/items/${itemId}`, { method: 'DELETE' }).then(r => r.json()),

  // Generate
  generateCategorySummary: (data: { category: string; article_titles: string[]; article_snippets: string[] }) => {
    const token = getToken();
    return fetch(`${API_BASE}/generate/category-summary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
  },
  generateMindmap: (data: { source_type: string; source_id: string }) => {
    const token = getToken();
    return fetch(`${API_BASE}/generate/mindmap`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
  },
  generateKG: (data: { source_type: string; source_id: string }) =>
    request('/generate/knowledge-graph', { method: 'POST', body: JSON.stringify(data) }).then(r => r.json()),
  generateBlog: (data: any) => {
    const token = getToken();
    return fetch(`${API_BASE}/generate/blog`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
  },
  generateArticle: (data: any) => {
    const token = getToken();
    return fetch(`${API_BASE}/generate/article`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
  },

  // Translate
  translate: (text: string) => {
    const token = getToken();
    return fetch(`${API_BASE}/generate/translate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text }),
    });
  },

  // Generated history
  getGenerated: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(`/generated${qs}`).then(r => r.json());
  },
  getGeneratedItem: (id: string) => request(`/generated/${id}`).then(r => r.json()),
  deleteGenerated: (id: string) => request(`/generated/${id}`, { method: 'DELETE' }).then(r => r.json()),
};
