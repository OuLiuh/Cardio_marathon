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