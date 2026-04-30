// frontend/src/api.js
const API_URL = import.meta.env.PROD ? '/api' : 'http://localhost:8000/api';

export const getUser = async (id) => {
  const res = await fetch(`${API_URL}/user/${id}`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error('Network error');
  }
  return res.json();
};

export const registerUser = async (id, username) => {
  const res = await fetch(`${API_URL}/user/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, username })
  });
  if (!res.ok) throw new Error('Registration failed');
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
    
    xhr.onload = () => {
      let json;
      try {
        json = JSON.parse(xhr.responseText);
      } catch (e) {
        // Если сервер вернул не JSON (например, HTML с ошибкой 413 Payload Too Large от Nginx)
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Attack failed');
  return json;
};

// --- НОВЫЕ ФУНКЦИИ МАГАЗИНА ---

export const fetchShop = async (userId) => {
    const res = await fetch(`${API_URL}/shop/${userId}`);
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Shop error');
    }
    return res.json();
};

export const buyItem = async (userId, itemKey) => {
    const res = await fetch(`${API_URL}/shop/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, item_key: itemKey })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Buy error');
    return data;
};

export const updateUsername = async (userId, newName) => {
  const res = await fetch(`${API_URL}/user/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: newName })
  });
  if (!res.ok) throw new Error('Update failed');
  return res.json();
};
