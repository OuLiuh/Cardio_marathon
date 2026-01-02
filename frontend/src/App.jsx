import { useState, useEffect } from 'react';
import { fetchRaidState, sendAttack, getUser, registerUser, updateUsername } from './api';
import './App.css';

function App() {
  // Состояния приложения
  const [screen, setScreen] = useState('loading'); // loading | rules | welcome | main
  const [currentUser, setCurrentUser] = useState(null);
  const [raid, setRaid] = useState(null);
  
  // Данные из Telegram
  const [tgData, setTgData] = useState({ id: null, first_name: 'Hero' });

  // Данные для форм
  const [loadingAction, setLoadingAction] = useState(false);
  const [message, setMessage] = useState('');
  const [editNameMode, setEditNameMode] = useState(false);
  const [newNickname, setNewNickname] = useState('');

  // Форма атаки (стейт)
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 35,
    calories: 300,
    distance_km: 5.0,
    avg_heart_rate: 140
  });

  // 1. Инициализация при старте
  useEffect(() => {
    // Получаем данные от Телеграм
    const tg = window.Telegram?.WebApp;
    let userId, firstName;

    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      userId = tg.initDataUnsafe.user.id;
      firstName = tg.initDataUnsafe.user.first_name;
      tg.expand(); // Раскрываем на весь экран
    } else {
      // Для тестов в браузере (без Телеграм)
      userId = 123456789; // Фейковый ID
      firstName = "BrowserUser";
    }

    setTgData({ id: userId, first_name: firstName });
    checkUserStatus(userId);
  }, []);

  // 2. Проверка: новичок или старичок?
  const checkUserStatus = async (id) => {
    const user = await getUser(id);
    if (user) {
      setCurrentUser(user);
      setNewNickname(user.username);
      setScreen('welcome'); // Старичок -> Экран приветствия
    } else {
      setScreen('rules');   // Новичок -> Правила
    }
  };

  // 3. Регистрация (Кнопка "Участвовать")
  const handleRegister = async () => {
    setLoadingAction(true);
    try {
      const user = await registerUser(tgData.id, tgData.first_name);
      setCurrentUser(user);
      setNewNickname(user.username);
      setScreen('main'); // Сразу в бой
      loadRaidData();
    } catch (e) {
      alert("Ошибка регистрации: " + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  // 4. Вход в игру (Кнопка "В бой")
  const handleEnterGame = () => {
    setScreen('main');
    loadRaidData();
  };

  // 5. Загрузка рейда (как раньше)
  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };

  // Поллинг рейда
  useEffect(() => {
    if (screen === 'main') {
      const interval = setInterval(loadRaidData, 3000);
      return () => clearInterval(interval);
    }
  }, [screen]);

  // 6. Атака
  const handleAttack = async () => {
    setLoadingAction(true);
    setMessage('');
    try {
      const result = await sendAttack({ user_id: currentUser.id, ...formData });
      setMessage(`💥 ${result.message} (+${result.gold_earned} 🪙)`);
      await loadRaidData();
    } catch (e) {
      setMessage('❌ Ошибка: ' + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  // 7. Смена ника
  const handleSaveName = async () => {
    try {
      const updated = await updateUsername(currentUser.id, newNickname);
      setCurrentUser(updated);
      setEditNameMode(false);
    } catch (e) {
      alert("Не удалось сменить имя");
    }
  };

  // Обработчик инпутов
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: name === 'sport_type' ? value : Number(value) }));
  };

  // --- РЕНДЕРИНГ ЭКРАНОВ ---

  if (screen === 'loading') {
    return <div className="container" style={{textAlign:'center', marginTop: 50}}>Загрузка...</div>;
  }

  // ЭКРАН 1: ПРАВИЛА (Для новых)
  if (screen === 'rules') {
    return (
      <div className="container">
        <div className="card">
          <h1>📜 Кодекс Марафона</h1>
          <p>Привет, {tgData.first_name}! Ты вступаешь в ряды Стражей Пульса.</p>
          <ul style={{textAlign:'left', lineHeight: '1.6'}}>
            <li>🛡️ <b>Цель:</b> Победить Титана Лени вместе с командой.</li>
            <li>🏃 <b>Норма:</b> 3 тренировки в неделю по 30+ минут.</li>
            <li>⚔️ <b>Битва:</b> Твои калории превращаются в урон.</li>
            <li>💰 <b>Прогресс:</b> Копи монеты и качай уровень.</li>
          </ul>
          <button className="attack-btn" onClick={handleRegister} disabled={loadingAction}>
            {loadingAction ? "Регистрация..." : "УЧАСТВОВАТЬ ✍️"}
          </button>
        </div>
      </div>
    );
  }

  // ЭКРАН 2: ПРИВЕТСТВИЕ (Для бывалых)
  if (screen === 'welcome') {
    return (
      <div className="container">
        <div className="card" style={{textAlign: 'center'}}>
          <h1>👋 С возвращением!</h1>
          <h2 style={{color: 'white', fontSize: '1.5em'}}>{currentUser.username}</h2>
          <p>Уровень: {currentUser.level} | Золото: {currentUser.gold}</p>
          <p>Титан ждет твоего удара.</p>
          <button className="attack-btn" onClick={handleEnterGame}>
            В АТАКУ! ⚔️
          </button>
        </div>
      </div>
    );
  }

  // ЭКРАН 3: ОСНОВНАЯ ИГРА (Как раньше, с добавкой смены ника)
  if (!raid) return <div className="container"><h2>Связь с базой...</h2></div>;
  const hpPercent = Math.max(0, (raid.current_hp / raid.max_hp) * 100);

  return (
    <div className="container">
      {/* Хедер с ником */}
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10}}>
        {editNameMode ? (
           <div style={{display: 'flex', gap: 5, width: '100%'}}>
             <input value={newNickname} onChange={(e) => setNewNickname(e.target.value)} />
             <button onClick={handleSaveName}>💾</button>
           </div>
        ) : (
           <div style={{color: '#aaa', fontSize: '0.9em'}} onClick={() => setEditNameMode(true)}>
             👤 {currentUser.username} ✏️
           </div>
        )}
        <div style={{color: '#ffd700'}}>💰 {currentUser.gold}</div>
      </div>

      {/* БОСС */}
      <div className="card">
        <h1>💀 {raid.boss_name}</h1>
        <div className="hp-container">
          <div className="hp-fill" style={{ width: `${hpPercent}%` }}></div>
          <div className="hp-text">{raid.current_hp} / {raid.max_hp} HP</div>
        </div>
        <div style={{textAlign: 'center', fontSize: '0.9em', color: '#888'}}>
           Онлайн: {raid.active_players_count}
        </div>
        {raid.active_debuffs?.armor_break && (
           <div className="debuff-badge" style={{marginTop: 5, display: 'inline-block'}}>🛡️ Броня пробита!</div>
        )}
      </div>

      {/* ФОРМА */}
      <div className="card">
        <h3>⚔️ Внести результат</h3>
        <div className="form-group">
          <label>Вид спорта:</label>
          <select name="sport_type" value={formData.sport_type} onChange={handleChange}>
            <option value="run">🏃 Бег</option>
            <option value="cycle">🚴 Велосипед</option>
            <option value="swim">🏊 Плавание</option>
            <option value="football">⚽ Футбол</option>
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

        <button className="attack-btn" onClick={handleAttack} disabled={loadingAction}>
          {loadingAction ? "..." : "НАНЕСТИ УДАР 👊"}
        </button>
        {message && <div style={{marginTop: 15, textAlign: 'center', color: '#4caf50', fontWeight: 'bold'}}>{message}</div>}
      </div>

      {/* ЛОГИ */}
      <div className="card">
        <h3>📜 Хроника</h3>
        {raid.recent_logs.map((log, i) => (
            <div key={i} className="log-item">
              <span className="log-highlight">{log.username}</span>: <span style={{color: '#ff4b1f'}}>{log.damage}</span> ({log.sport_type})
            </div>
        ))}
      </div>
    </div>
  );
}

export default App;