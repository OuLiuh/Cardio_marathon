// frontend/src/api.js

// Получение состояния рейда (Босс, ХП, Логи)
export const fetchRaidState = async () => {
  try {
    const response = await fetch('/api/raid/current');
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch raid state:", error);
    return null;
  }
};

// Отправка атаки
export const sendAttack = async (workoutData) => {
  try {
    const response = await fetch('/api/attack', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(workoutData),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Attack failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error("Attack error:", error);
    throw error;
  }
};

// Проверка юзера
export const getUser = async (userId) => {
  try {
    const response = await fetch(`/api/user/${userId}`);
    if (response.status === 404) return null; // Юзера нет
    if (!response.ok) throw new Error('Error checking user');
    return await response.json();
  } catch (error) {
    console.error("Get User Error:", error);
    return null;
  }
};

// Регистрация
export const registerUser = async (userId, username) => {
  const response = await fetch('/api/user/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: userId, username: username }),
  });
  if (!response.ok) throw new Error('Registration failed');
  return await response.json();
};

// Обновление ника
export const updateUsername = async (userId, newName) => {
  const response = await fetch(`/api/user/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: newName }),
  });
  if (!response.ok) throw new Error('Update failed');
  return await response.json();
};

// ... getUser, registerUser ...

export const fetchShop = async (userId) => {
    const res = await fetch(`${API_URL}/shop/${userId}`);
    if (!res.ok) throw new Error('Shop error');
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