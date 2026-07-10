// frontend/src/api.js
const API_URL = import.meta.env.PROD ? '/api' : 'http://localhost:8000/api';
const TOKEN_KEY = 'pg_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
};

const authHeaders = (extra = {}) => {
  const headers = { ...extra };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
};

const parseError = async (res, fallback) => {
  const data = await res.json().catch(() => ({}));
  const detail = data.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || d).join('; ');
  return fallback;
};

export const register = async (username, password) => {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Ошибка регистрации'));
  const data = await res.json();
  setToken(data.access_token);
  return data.user;
};

export const login = async (username, password) => {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Ошибка входа'));
  const data = await res.json();
  setToken(data.access_token);
  return data.user;
};

export const getMe = async () => {
  const token = getToken();
  if (!token) return null;
  const res = await fetch(`${API_URL}/user/me`, {
    headers: authHeaders(),
  });
  if (res.status === 401) {
    clearAuth();
    return null;
  }
  if (!res.ok) throw new Error(await parseError(res, 'Не удалось загрузить профиль'));
  return res.json();
};

export const fetchRaidState = async () => {
  try {
    const res = await fetch(`${API_URL}/raid/current`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error(e);
    return null;
  }
};

export const scanWorkout = (formData) => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_URL}/scan-workout`, true);
    const token = getToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.onload = () => {
      let json;
      try {
        json = JSON.parse(xhr.responseText);
      } catch (e) {
        console.error('Non-JSON response:', xhr.responseText);
        if (xhr.status === 413) {
          return reject(new Error('Файл слишком большой. Пожалуйста, сожмите фото.'));
        }
        return reject(new Error(`Ошибка сервера (${xhr.status}). Попробуйте позже.`));
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(json);
      } else {
        reject(new Error(json.detail || 'OCR failed'));
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error during OCR. Please check your connection.'));
    };

    xhr.send(formData);
  });
};

export const sendAttack = async (data) => {
  const res = await fetch(`${API_URL}/attack`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Attack failed');
  return json;
};

export const fetchShop = async () => {
  const res = await fetch(`${API_URL}/shop`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await parseError(res, 'Shop error'));
  }
  return res.json();
};

export const buyItem = async (itemKey) => {
  const res = await fetch(`${API_URL}/shop/buy`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ item_key: itemKey }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Buy error');
  return data;
};
