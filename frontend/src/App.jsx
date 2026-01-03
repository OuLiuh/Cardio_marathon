import { useState, useEffect } from 'react';
import { fetchRaidState, sendAttack, getUser, registerUser, updateUsername } from './api';
import './App.css';

function App() {
  // --- СОСТОЯНИЕ ---
  const [screen, setScreen] = useState('loading'); // loading | rules | welcome | main
  const [currentUser, setCurrentUser] = useState(null);
  const [raid, setRaid] = useState(null);
  
  // Данные Telegram
  const [tgData, setTgData] = useState({ id: null, first_name: 'Hero' });

  // Состояние формы атаки
  const [showAttackForm, setShowAttackForm] = useState(false);
  const [loadingAction, setLoadingAction] = useState(false);
  const [message, setMessage] = useState('');
  
  // Данные формы
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 30,
    calories: 300,
    distance_km: 5.0,
    avg_heart_rate: 140
  });

  // --- ЭФФЕКТЫ ---

  // 1. Инициализация
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    let userId, firstName;

    if (tg?.initDataUnsafe?.user) {
      userId = tg.initDataUnsafe.user.id;
      firstName = tg.initDataUnsafe.user.first_name;
      tg.expand(); // На весь экран
    } else {
      // DEV MODE: Фейковые данные для браузера
      userId = 777000; 
      firstName = "DevHero";
    }

    setTgData({ id: userId, first_name: firstName });
    checkUserStatus(userId);
  }, []);

  // 2. Поллинг (обновление данных раз в 3 сек)
  useEffect(() => {
    if (screen === 'main') {
      loadRaidData(); // Первая загрузка
      const interval = setInterval(loadRaidData, 3000);
      return () => clearInterval(interval);
    }
  }, [screen]);

  // --- ЛОГИКА ---

  const checkUserStatus = async (id) => {
    try {
      const user = await getUser(id);
      if (user) {
        setCurrentUser(user);
        setScreen('welcome');
      } else {
        setScreen('rules');
      }
    } catch (e) {
      console.error("Connection error", e);
      setScreen('rules'); // Fallback
    }
  };

  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };

  const handleRegister = async () => {
    haptic('impact');
    setLoadingAction(true);
    try {
      const user = await registerUser(tgData.id, tgData.first_name);
      setCurrentUser(user);
      setScreen('main');
      await loadRaidData();
    } catch (e) {
      alert("Ошибка: " + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleEnterGame = () => {
    haptic('selection');
    setScreen('main');
  };

  const handleAttack = async () => {
    haptic('notification');
    setLoadingAction(true);
    setMessage('');
    try {
      const result = await sendAttack({ user_id: currentUser.id, ...formData });
      
      // Обновляем золото пользователя локально, чтобы не ждать поллинга
      setCurrentUser(prev => ({
        ...prev,
        xp: prev.xp + result.xp_earned,
        // Если золото пришло в ответе (босс умер), обновляем
        gold: prev.gold + result.gold_earned
      }));

      setMessage(`✅ ${result.message}`);
      setShowAttackForm(false); // Закрываем форму после удара
      await loadRaidData(); // Обновляем босса сразу
    } catch (e) {
      setMessage('❌ Ошибка: ' + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  // Хелпер для вибрации (если в TG)
  const haptic = (type) => {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'impact') window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
      if (type === 'notification') window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      if (type === 'selection') window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
  };

  // Обработчик инпутов
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: name === 'sport_type' ? value : Number(value) }));
  };

  const setSport = (type) => {
    setFormData(prev => ({ ...prev, sport_type: type }));
    haptic('selection');
  };

  // Математика для орбиты
  const getPosition = (index, total, radius) => {
    if (total === 0) return { x: 0, y: 0 };
    const angle = (index / total) * 2 * Math.PI; 
    const x = Math.cos(angle - Math.PI / 2) * radius;
    const y = Math.sin(angle - Math.PI / 2) * radius;
    return { x, y };
  };

  // --- РЕНДЕР КОМПОНЕНТЫ ---

  // 1. Бейджи характеристик босса
  const renderBossTraits = (traits) => {
    if (!traits) return null;
    const badges = [];
    if (traits.armor_reduction) badges.push(<span key="armor" className="trait-badge armor">🛡️ Броня</span>);
    if (traits.evasion_chance) badges.push(<span key="evasion" className="trait-badge evasion">💨 Ловкий</span>);
    if (traits.regen_daily_percent) badges.push(<span key="regen" className="trait-badge toxic">☣️ Токсик</span>);
    return badges.length ? <div className="traits-container">{badges}</div> : null;
  };

  // --- ЭКРАНЫ ---

  if (screen === 'loading') return <div className="center-screen">Загрузка данных...</div>;

  if (screen === 'rules') {
    return (
      <div className="container fade-in">
        <div className="card">
          <h1>📜 Кодекс</h1>
          <p>Привет, {tgData.first_name}! Титан Лени угрожает нам.</p>
          <ul className="rules-list">
            <li>🏃 <b>Тренируйся:</b> Бег, Вело, Плаванье.</li>
            <li>🔥 <b>Сжигай:</b> Калории = Урон по боссу.</li>
            <li>💰 <b>Зарабатывай:</b> Золото дают за победу над боссом.</li>
            <li>📈 <b>Доля:</b> Чем больше твой вклад, тем больше награда.</li>
          </ul>
          <button className="attack-btn" onClick={handleRegister} disabled={loadingAction}>
            {loadingAction ? "Регистрация..." : "Вступить в отряд"}
          </button>
        </div>
      </div>
    );
  }

  if (screen === 'welcome') {
    return (
      <div className="container fade-in">
        <div className="card center-text">
          <h1>Привет, {currentUser.username}!</h1>
          <div className="stats-row">
            <div>⭐ Lv. {currentUser.level}</div>
            <div>💰 {currentUser.gold}</div>
          </div>
          <p>Твоя команда уже сражается.</p>
          <button className="attack-btn" onClick={handleEnterGame}>В БОЙ ⚔️</button>
        </div>
      </div>
    );
  }

  // --- ОСНОВНОЙ ЭКРАН ---
  if (!raid) return <div className="center-screen">Поиск сигнала с арены...</div>;

  const players = raid.participants || [];
  const radius = 100; // Радиус орбиты

  return (
    <div className="container main-layout">
      
      {/* 1. Хедер */}
      <header className="game-header">
        <div className="user-info">
          <span className="lvl-badge">{currentUser.level}</span>
          <span>{currentUser.username}</span>
        </div>
        <div className="gold-info">
          💰 {currentUser.gold}
        </div>
      </header>

      {/* 2. Арена */}
      <div className="battle-arena">
        {/* Босс */}
        <div className={`boss-center ${raid.boss_type}`}>
          <div className="boss-emoji">👹</div>
        </div>

        {/* Игроки */}
        {players.map((p, index) => {
           const { x, y } = getPosition(index, players.length, radius);
           return (
             <div key={index} className="player-orbit" style={{ transform: `translate(${x}px, ${y}px)` }}>
               <div className="player-avatar" style={{backgroundColor: p.avatar_color}}>
                 {p.username.charAt(0).toUpperCase()}
               </div>
             </div>
           );
        })}
      </div>

      {/* 3. Инфо Босса */}
      <div className="card boss-card">
        <h2 className="boss-name">{raid.boss_name}</h2>
        {renderBossTraits(raid.traits)}
        
        <div className="hp-wrapper">
          <div className="hp-container">
            <div className="hp-fill" style={{ width: `${Math.max(0, (raid.current_hp / raid.max_hp) * 100)}%` }}></div>
          </div>
          <span className="hp-numbers">{raid.current_hp} / {raid.max_hp} HP</span>
        </div>

        {raid.active_debuffs?.armor_break && (
           <div className="debuff-notification">🔨 БРОНЯ РАСКОЛОТА! (+15% урона)</div>
        )}
      </div>

      {/* 4. Форма Атаки (Улучшенная) */}
      <div className="card action-card">
        {!showAttackForm ? (
          <button className="attack-btn primary" onClick={() => setShowAttackForm(true)}>
            ВНЕСТИ ТРЕНИРОВКУ 📝
          </button>
        ) : (
          <div className="attack-form fade-in">
            <h3>Тип тренировки</h3>
            <div className="sport-grid">
              <button className={formData.sport_type === 'run' ? 'active' : ''} onClick={() => setSport('run')}>
                🏃<br/>Бег
              </button>
              <button className={formData.sport_type === 'cycle' ? 'active' : ''} onClick={() => setSport('cycle')}>
                🚴<br/>Вело
              </button>
              <button className={formData.sport_type === 'swim' ? 'active' : ''} onClick={() => setSport('swim')}>
                🏊<br/>Вода
              </button>
              <button className={formData.sport_type === 'football' ? 'active' : ''} onClick={() => setSport('football')}>
                ⚽<br/>Спорт
              </button>
            </div>

            <div className="inputs-grid">
              <label>
                Время (мин)
                <input type="number" name="duration_minutes" value={formData.duration_minutes} onChange={handleChange} />
              </label>
              <label>
                Калории
                <input type="number" name="calories" value={formData.calories} onChange={handleChange} />
              </label>
            </div>
            
            <div className="inputs-grid">
              <label>
                Дистанция (км)
                <input type="number" name="distance_km" value={formData.distance_km} onChange={handleChange} />
              </label>
               <label>
                Ср. Пульс
                <input type="number" name="avg_heart_rate" value={formData.avg_heart_rate} onChange={handleChange} />
              </label>
            </div>

            <div className="form-actions">
              <button className="cancel-btn" onClick={() => setShowAttackForm(false)}>Отмена</button>
              <button className="attack-btn" onClick={handleAttack} disabled={loadingAction}>
                {loadingAction ? "Отправка..." : "АТАКОВАТЬ 👊"}
              </button>
            </div>
          </div>
        )}
        
        {message && <div className="game-message">{message}</div>}
      </div>

      {/* 5. Логи */}
      <div className="logs-container">
        <h4>Хроники битвы:</h4>
        {raid.recent_logs.map((log, i) => (
            <div key={i} className="log-item">
              <span className="log-user">{log.username}</span> 
              <span className="log-action">
                {log.sport_type === 'swim' ? 'проплыл' : 'набегал'} на 
                <span className="log-dmg"> -{log.damage}</span>
              </span>
            </div>
        ))}
      </div>

    </div>
  );
}

export default App;