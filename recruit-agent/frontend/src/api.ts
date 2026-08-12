import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // AI 调用可能含上游 LLM，放宽超时
  const url = config.url || '';
  if (url.startsWith('/ai/') || url.includes('/parse-resume')) {
    config.timeout = 120000;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.message || err.message || '请求失败';
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject({ ...err, message, data: err.response?.data });
  }
);

export default api;

export type UserInfo = {
  id: string;
  username: string;
  name: string;
  role: string;
  roleLabel?: string;
  orgId?: string | null;
  orgName?: string;
  dataScope?: string;
};
