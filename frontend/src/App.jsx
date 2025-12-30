// frontend/src/App.jsx
import { useState, useEffect } from 'react';
import { fetchRaidState, sendAttack } from './api';
import './App.css';

function App() {
  const [raid, setRaid] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Тестовый ID пользователя (сохраняем в браузере)
  const [userId] = useState(() => {
    const saved = localStorage.getItem('test_user_id');
    if (saved) return parseInt(saved);
    const newId = Math.floor(Math.random() * 1000000);
    localStorage.setItem('test_user_id', newId);
    return newId;
  });

  // Данные формы (симуляция трекера)
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 35,
    calories: 300,
    distance_km: 5.0,
    avg_heart_rate: 140
  });

  // 1. Polling: Опрос сервера каждые 3 секунды
  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };

  useEffect(() => {
    loadRaidData(); // Сразу при загрузке
    const interval = setInterval(loadRaidData, 3000); // И потом каждые 3 сек
    return () => clearInterval(interval);
  }, []);

  // 2. Обработка атаки
  const handleAttack = async () => {
    setLoading(true);
    setMessage('');
    try {
      const result = await sendAttack({
        user_id: userId,
        ...formData
      });
      setMessage(`💥 ${result.message} (+${result.gold_earned} 🪙)`);
      await loadRaidData(); // Обновляем HP сразу
    } catch (e) {
      setMessage('❌ Ошибка атаки: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'sport_type' ? value : Number(value)
    }));
  };

  if (!raid) return <div className="container"><h2>Загрузка связи с Титанами...</h2></div>;

  // Рассчет процента HP
  const hpPercent = Math.max(0, (raid.current_hp / raid.max_hp) * 100);

  return (
    <div className="container">
      {/* --- БЛОК БОССА --- */}
      <div className="card">
        <h1>💀 {raid.boss_name}</h1>
        
        <div className="hp-container">
          <div className="hp-fill" style={{ width: `${hpPercent}%` }}></div>
          <div className="hp-text">{raid.current_hp} / {raid.max_hp} HP</div>
        </div>
        
        <div style={{textAlign: 'center', fontSize: '0.9em', color: '#888'}}>
           Игроков онлайн: {raid.active_players_count}
        </div>

        {/* Дебаффы */}
        {raid.active_debuffs && Object.keys(raid.active_debuffs).length > 0 && (
          <div style={{marginTop: 10, textAlign: 'center'}}>
            {raid.active_debuffs.armor_break && (
              <span className="debuff-badge">🛡️ Броня пробита (+15% урона)</span>
            )}
          </div>
        )}
      </div>

      {/* --- БЛОК СИМУЛЯЦИИ АТАКИ --- */}
      <div className="card">
        <h3>⚔️ Симулятор Тренировки</h3>
        <p style={{fontSize: '0.8em', color: '#aaa'}}>Твой ID: {userId}</p>
        
        <div className="form-group">
          <label>Вид спорта:</label>
          <select name="sport_type" value={formData.sport_type} onChange={handleChange}>
            <option value="run">🏃 Бег (Баланс)</option>
            <option value="cycle">🚴 Велосипед (Много атак)</option>
            <option value="swim">🏊 Плавание (Пробитие брони)</option>
            <option value="football">⚽ Футбол (Крит шанс)</option>
          </select>
        </div>

        <div style={{display: 'flex', gap: '10px'}}>
            <div className="form-group" style={{flex: 1}}>
            <label>Время (мин):</label>
            <input type="number" name="duration_minutes" value={formData.duration_minutes} onChange={handleChange} />
            </div>
            <div className="form-group" style={{flex: 1}}>
            <label>Ккал:</label>
            <input type="number" name="calories" value={formData.calories} onChange={handleChange} />
            </div>
        </div>

        <div style={{display: 'flex', gap: '10px'}}>
            <div className="form-group" style={{flex: 1}}>
            <label>Км:</label>
            <input type="number" name="distance_km" value={formData.distance_km} onChange={handleChange} />
            </div>
            <div className="form-group" style={{flex: 1}}>
            <label>Пульс:</label>
            <input type="number" name="avg_heart_rate" value={formData.avg_heart_rate} onChange={handleChange} />
            </div>
        </div>

        <button className="attack-btn" onClick={handleAttack} disabled={loading}>
          {loading ? "Расчет урона..." : "НАНЕСТИ УДАР 👊"}
        </button>
        
        {message && <div style={{marginTop: 15, textAlign: 'center', color: '#4caf50', fontWeight: 'bold'}}>{message}</div>}
      </div>

      {/* --- ЛОГ БИТВЫ --- */}
      <div className="card">
        <h3>📜 История Битвы</h3>
        {raid.recent_logs.length === 0 ? (
          <p style={{textAlign: 'center'}}>Пока тихо...</p>
        ) : (
          raid.recent_logs.map((log, index) => (
            <div key={index} className="log-item">
              <span className="log-highlight">{log.username}</span> 
              {' '}ударил на{' '} 
              <span style={{color: '#ff4b1f', fontWeight: 'bold'}}>{log.damage}</span>
              {' '}используя {log.sport_type === 'run' ? '🏃' : log.sport_type === 'cycle' ? '🚴' : log.sport_type === 'swim' ? '🏊' : '⚽'}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default App;