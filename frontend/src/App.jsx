import { useState, useEffect } from 'react';
import { fetchRaidState, sendAttack, getUser, registerUser, fetchShop, buyItem } from './api';
import './App.css';

function App() {
  const [screen, setScreen] = useState('loading'); // loading | rules | welcome | main | shop
  const [currentUser, setCurrentUser] = useState(null);
  const [raid, setRaid] = useState(null);
  const [shopItems, setShopItems] = useState([]);
  
  const [tgData, setTgData] = useState({ id: null, first_name: 'Hero' });
  const [showAttackForm, setShowAttackForm] = useState(false);
  const [loadingAction, setLoadingAction] = useState(false);
  const [message, setMessage] = useState('');
  
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 30,
    calories: 0,
    distance_km: 0.0,
    avg_heart_rate: 0
  });

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    let userId, firstName;
    if (tg?.initDataUnsafe?.user) {
      userId = tg.initDataUnsafe.user.id;
      firstName = tg.initDataUnsafe.user.first_name;
      tg.expand();
    } else {
      userId = 777000; firstName = "DevHero";
    }
    setTgData({ id: userId, first_name: firstName });
    checkUserStatus(userId);
  }, []);

  useEffect(() => {
    if (screen === 'main') {
      loadRaidData();
      const interval = setInterval(loadRaidData, 3000);
      return () => clearInterval(interval);
    }
  }, [screen]);

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
      setScreen('rules');
    }
  };

  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };
  
  const openShop = async () => {
    haptic('selection');
    setLoadingAction(true);
    try {
        const items = await fetchShop(currentUser.id);
        setShopItems(items);
        setScreen('shop');
    } catch(e) {
        alert("Ошибка магазина");
    } finally {
        setLoadingAction(false);
    }
  };

  const handleBuy = async (itemKey) => {
      haptic('selection');
      try {
          const res = await buyItem(currentUser.id, itemKey);
          setCurrentUser(prev => ({...prev, gold: res.gold_left}));
          // Обновляем список
          const items = await fetchShop(currentUser.id);
          setShopItems(items);
          haptic('notification');
      } catch(e) {
          alert("Ошибка: " + e.message);
          haptic('impact');
      }
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
      setCurrentUser(prev => ({
        ...prev,
        xp: prev.xp + result.xp_earned,
        gold: prev.gold + result.gold_earned
      }));
      setMessage(`✅ ${result.message}`);
      setShowAttackForm(false);
      await loadRaidData();
    } catch (e) {
      setMessage('❌ Ошибка: ' + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  const haptic = (type) => {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'impact') window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
      if (type === 'notification') window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      if (type === 'selection') window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: name === 'sport_type' ? value : Number(value) }));
  };

  const setSport = (type) => {
    setFormData(prev => ({ ...prev, sport_type: type }));
    haptic('selection');
  };
  
  const renderFormInputs = () => {
    const { sport_type } = formData;
    const showDuration = sport_type === 'run' || sport_type === 'cycle';
    const showDistance = sport_type === 'run' || sport_type === 'cycle' || sport_type === 'swim';
    const showCalories = sport_type === 'football';

    return (
      <div className="inputs-grid">
          {showDuration && (
            <label>Время (мин) <input type="number" name="duration_minutes" value={formData.duration_minutes} onChange={handleChange} placeholder="30" /></label>
          )}
          {showCalories && (
            <label>Калории <input type="number" name="calories" value={formData.calories} onChange={handleChange} placeholder="300" /></label>
          )}
           {showDistance && (
            <label>Дистанция (км) <input type="number" name="distance_km" value={formData.distance_km} onChange={handleChange} placeholder="5.0" /></label>
          )}
      </div>
    );
  };
  
  // --- RENDERS ---

  if (screen === 'loading') return <div className="center-screen">Загрузка данных...</div>;

  if (screen === 'shop') {
      return (
          <div className="container fade-in">
              <div className="header-row">
                  <button className="back-btn" onClick={() => setScreen('main')}>← Назад</button>
                  <div className="gold-info">💰 {currentUser.gold}</div>
              </div>
              <h1>🛒 Магазин</h1>
              <div className="shop-list">
                  {shopItems.map(item => (
                      <div key={item.key} className={`shop-item ${item.is_locked ? 'locked' : ''} ${item.sport_type}`}>
                          <div className="item-info">
                              <h3>{item.name} {item.current_level > 0 && <span className="lvl-tag">Lvl {item.current_level}</span>}</h3>
                              <p>{item.description}</p>
                              {item.is_locked && <small className="lock-reason">🔒 Требуются улучшения 10 ур.</small>}
                          </div>
                          <div className="item-action">
                              {item.is_maxed ? (
                                  <span className="max-tag">MAX</span>
                              ) : (
                                  <button 
                                    className="buy-btn" 
                                    disabled={item.is_locked || currentUser.gold < item.next_price}
                                    onClick={() => handleBuy(item.key)}
                                  >
                                      {item.next_price} 💰
                                  </button>
                              )}
                          </div>
                      </div>
                  ))}
              </div>
          </div>
      )
  }

  // --- WELCOME & RULES screens are same ---
  if (screen === 'rules') {
    return (
      <div className="container fade-in">
        <div className="card">
          <h1>📜 Кодекс</h1>
          <p>Привет, {tgData.first_name}! Титан Лени угрожает нам.</p>
          <ul className="rules-list">
            <li>🏃 <b>Тренируйся:</b> Бег, Вело, Плаванье.</li>
            <li>🔥 <b>Сжигай:</b> Калории = Урон по боссу.</li>
            <li>💰 <b>Зарабатывай:</b> Золото делят победители.</li>
          </ul>
          <button className="attack-btn" onClick={handleRegister} disabled={loadingAction}>{loadingAction ? "..." : "Вступить"}</button>
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
            <button className="attack-btn" onClick={handleEnterGame}>В БОЙ ⚔️</button>
          </div>
        </div>
      );
  }

  if (!raid) return <div className="center-screen">Поиск сигнала...</div>;

  return (
    <div className="container main-layout">
      <header className="game-header">
        <div className="user-info">
          <span className="lvl-badge">{currentUser.level}</span>
          <span>{currentUser.username}</span>
        </div>
        <div className="gold-info">💰 {currentUser.gold}</div>
      </header>

      {/* SHOP BUTTON */}
      <button className="shop-btn-floating" onClick={openShop}>🛒</button>

      <div className="battle-arena">
        <div className={`boss-center ${raid.boss_type}`}>
          <div className="boss-emoji">👹</div>
        </div>
        {raid.participants?.map((p, index) => {
             // ... orbit logic same as before (inline or helper) ...
             const total = raid.participants.length;
             const angle = (index / total) * 2 * Math.PI; 
             const x = Math.cos(angle - Math.PI / 2) * 100;
             const y = Math.sin(angle - Math.PI / 2) * 100;
           return (
             <div key={index} className="player-orbit" style={{ transform: `translate(${x}px, ${y}px)` }}>
               <div className="player-avatar" style={{backgroundColor: p.avatar_color}}>{p.username.charAt(0).toUpperCase()}</div>
             </div>
           );
        })}
      </div>

      <div className="card boss-card">
        <h2 className="boss-name">{raid.boss_name}</h2>
        
        <div className="hp-wrapper">
          <div className="hp-container">
            <div className="hp-fill" style={{ width: `${Math.max(0, (raid.current_hp / raid.max_hp) * 100)}%` }}></div>
          </div>
          <span className="hp-numbers">{raid.current_hp} / {raid.max_hp} HP</span>
        </div>
        {raid.active_debuffs?.armor_break && <div className="debuff-notification">🔨 БРОНЯ РАСКОЛОТА!</div>}
      </div>

      <div className="card action-card">
        {!showAttackForm ? (
          <button className="attack-btn primary" onClick={() => setShowAttackForm(true)}>ВНЕСТИ ТРЕНИРОВКУ 📝</button>
        ) : (
          <div className="attack-form fade-in">
            <h3>Тип тренировки</h3>
            <div className="sport-grid">
              <button className={formData.sport_type === 'run' ? 'active' : ''} onClick={() => setSport('run')}>🏃<br/>Бег</button>
              <button className={formData.sport_type === 'cycle' ? 'active' : ''} onClick={() => setSport('cycle')}>🚴<br/>Вело</button>
              <button className={formData.sport_type === 'swim' ? 'active' : ''} onClick={() => setSport('swim')}>🏊<br/>Вода</button>
              <button className={formData.sport_type === 'football' ? 'active' : ''} onClick={() => setSport('football')}>⚽<br/>Спорт</button>
            </div>
            {renderFormInputs()}
            <div className="form-actions">
              <button className="cancel-btn" onClick={() => setShowAttackForm(false)}>Отмена</button>
              <button className="attack-btn" onClick={handleAttack} disabled={loadingAction}>АТАКОВАТЬ 👊</button>
            </div>
          </div>
        )}
        {message && <div className="game-message">{message}</div>}
      </div>

      <div className="logs-container">
        {raid.recent_logs.map((log, i) => (
            <div key={i} className="log-item">
              <span className="log-user">{log.username}</span> 
              <span className="log-action">нанес <span className="log-dmg">-{log.damage}</span></span>
            </div>
        ))}
      </div>
    </div>
  );
}

export default App;