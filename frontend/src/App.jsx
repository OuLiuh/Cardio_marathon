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

  // Вспомогательная функция для расчета координат круга
  const getPosition = (index, total, radius) => {
    const angle = (index / total) * 2 * Math.PI; // Угол в радианах
    const x = Math.cos(angle - Math.PI / 2) * radius; // -PI/2 чтобы первый был сверху
    const y = Math.sin(angle - Math.PI / 2) * radius;
    return { x, y };
  };

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

  // ЭКРАН 3: ОСНОВНАЯ ИГРА
  if (!raid) return <div className="container"><h2>Загрузка арены...</h2></div>;
  
  // Если массив participants вдруг пустой (старый бэк), делаем пустой массив
  const players = raid.participants || [];
  const radius = 110; // Радиус орбиты в пикселях

  return (
    <div className="container" style={{maxWidth: '600px'}}> 
      
      {/* --- ХЕДЕР (Ник и Золото) --- */}
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, padding: '0 10px'}}>
        <div style={{color: '#aaa', fontSize: '0.9em'}}>
             👤 {currentUser.username} (Lvl {currentUser.level})
        </div>
        <div style={{color: '#ffd700'}}>💰 {currentUser.gold}</div>
      </div>

      {/* --- АРЕНА (ВИЗУАЛИЗАЦИЯ) --- */}
      <div className="battle-arena">
        
        {/* БОСС (Центр) */}
        <div className="boss-center">
          <div className="boss-emoji">👹</div>
          <div style={{fontSize: '10px', color: '#fff', marginTop: 5}}>
             {raid.current_hp} HP
          </div>
        </div>

        {/* ИГРОКИ (По кругу) */}
        {players.map((p, index) => {
           const { x, y } = getPosition(index, players.length, radius);
           return (
             <div 
                key={index} 
                className="player-orbit" 
                style={{ transform: `translate(${x}px, ${y}px)` }}
             >
               <div className="player-avatar" style={{backgroundColor: p.avatar_color}}>
                 {p.username.charAt(0).toUpperCase()}
               </div>
               <div className="player-info">
                 {p.username}<br/>
                 <span style={{color: '#ffd700'}}>Lv.{p.level}</span>
               </div>
             </div>
           );
        })}
      </div>

      {/* --- БЛОК ХП БАРА --- */}
      <div className="card" style={{marginTop: '-20px', position: 'relative', zIndex: 20}}>
        <h3>{raid.boss_name}</h3>
        <div className="hp-container">
            {/* Считаем % HP */}
          <div className="hp-fill" style={{ width: `${Math.max(0, (raid.current_hp / raid.max_hp) * 100)}%` }}></div>
        </div>
        {raid.active_debuffs?.armor_break && (
           <div style={{textAlign: 'center'}}><span className="debuff-badge">🛡️ БРОНЯ ПРОБИТА!</span></div>
        )}
      </div>

      {/* --- КНОПКА АТАКИ (ФОРМА) --- */}
      {/* ... Скрываем форму в аккордеон или оставляем как есть, давай оставим простой вариант ... */}
      <div className="card">
         {/* ... (Тут код формы из предыдущего ответа: селект спорта, инпуты и кнопка) ... */}
         <h3>⚔️ Атаковать</h3>
         <div className="form-group">
            <select name="sport_type" value={formData.sport_type} onChange={handleChange} style={{marginBottom: 10}}>
              <option value="run">🏃 Бег</option>
              <option value="cycle">🚴 Велосипед</option>
              <option value="swim">🏊 Плавание</option>
              <option value="football">⚽ Футбол</option>
            </select>
            {/* Упрощенные инпуты для экономии места */}
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10}}>
               <input type="number" name="duration_minutes" placeholder="Мин" value={formData.duration_minutes} onChange={handleChange} />
               <input type="number" name="calories" placeholder="Ккал" value={formData.calories} onChange={handleChange} />
            </div>
         </div>
         <button className="attack-btn" onClick={handleAttack} disabled={loadingAction} style={{marginTop: 10}}>
          {loadingAction ? "..." : "УДАРИТЬ 👊"}
        </button>
        {message && <div style={{marginTop: 10, textAlign: 'center', color: '#4caf50'}}>{message}</div>}
      </div>

      {/* --- ЛОГИ (Снизу) --- */}
      <div className="card">
        <h4 style={{marginTop: 0, color: '#888'}}>Последние удары:</h4>
        {raid.recent_logs.map((log, i) => (
            <div key={i} style={{fontSize: '0.8em', borderBottom: '1px solid #333', padding: '5px 0'}}>
              <b>{log.username}</b>: -{log.damage} ({log.sport_type})
            </div>
        ))}
      </div>

    </div>
  );
}

export default App;