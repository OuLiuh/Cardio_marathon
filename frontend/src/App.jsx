/**
 * App.jsx — Pulse Guardian (standalone web app)
 */

import { useState, useEffect } from 'react';
import {
  fetchRaidState,
  sendAttack,
  getMe,
  register,
  login,
  fetchShop,
  buyItem,
  scanWorkout,
  clearAuth,
  getToken,
} from './api';
import './App.css';

function App() {
  const [screen, setScreen] = useState('loading');
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authForm, setAuthForm] = useState({ username: '', password: '' });
  const [authError, setAuthError] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [raid, setRaid] = useState(null);
  const [shopItems, setShopItems] = useState([]);
  const [showAttackForm, setShowAttackForm] = useState(false);
  const [loadingAction, setLoadingAction] = useState(false);
  const [message, setMessage] = useState('');
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState('');
  const [parsedData, setParsedData] = useState(null);
  const [confirmMode, setConfirmMode] = useState(false);
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 30,
    calories: 0,
    distance_km: 0.0,
    avg_heart_rate: 0,
  });

  useEffect(() => {
    const boot = async () => {
      if (!getToken()) {
        setScreen('auth');
        return;
      }
      try {
        const user = await getMe();
        if (user) {
          setCurrentUser(user);
          setScreen('welcome');
        } else {
          setScreen('auth');
        }
      } catch {
        clearAuth();
        setScreen('auth');
      }
    };
    boot();
  }, []);

  useEffect(() => {
    if (screen === 'main') {
      loadRaidData();
      const interval = setInterval(loadRaidData, 3000);
      return () => clearInterval(interval);
    }
  }, [screen]);

  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setLoadingAction(true);
    try {
      const { username, password } = authForm;
      if (!username.trim() || !password) {
        setAuthError('Введите имя и пароль');
        return;
      }
      const user =
        authMode === 'register'
          ? await register(username.trim(), password)
          : await login(username.trim(), password);
      setCurrentUser(user);
      setScreen(authMode === 'register' ? 'rules' : 'welcome');
    } catch (err) {
      setAuthError(err.message || 'Ошибка');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleLogout = () => {
    clearAuth();
    setCurrentUser(null);
    setRaid(null);
    setAuthForm({ username: '', password: '' });
    setScreen('auth');
  };

  const openShop = async () => {
    setLoadingAction(true);
    try {
      const items = await fetchShop();
      setShopItems(items);
      setScreen('shop');
    } catch (e) {
      alert('Ошибка магазина: ' + (e.message || 'Неизвестная ошибка'));
    } finally {
      setLoadingAction(false);
    }
  };

  const handleBuy = async (itemKey) => {
    try {
      const res = await buyItem(itemKey);
      setCurrentUser((prev) => ({ ...prev, gold: res.new_gold ?? prev.gold }));
      const items = await fetchShop();
      setShopItems(items);
    } catch (e) {
      alert('Ошибка: ' + e.message);
    }
  };

  const handleEnterGame = () => {
    setScreen('main');
  };

  const handleParse = async () => {
    if (!photo) return;
    setLoadingAction(true);
    setMessage('');

    const formDataObj = new FormData();
    formDataObj.append('file', photo);
    formDataObj.append('sport_type', formData.sport_type);

    try {
      const result = await scanWorkout(formDataObj);
      setParsedData(result);
      setConfirmMode(true);
    } catch (e) {
      const errorText = e.message || 'Ошибка';
      const parts = errorText.split('\n\n📄 Распознанный текст:\n');
      const mainError = parts[0];
      const recognizedText = parts[1] || null;

      if (recognizedText) {
        setMessage({ type: 'error', main: mainError, rawText: recognizedText });
      } else {
        setMessage(`❌ ${mainError}`);
      }
    } finally {
      setLoadingAction(false);
    }
  };

  const handleConfirm = () => {
    setFormData((prev) => ({ ...prev, ...parsedData }));
    setShowAttackForm(false);
    handleAttack(parsedData);
  };

  const handleRetry = () => {
    setConfirmMode(false);
    setParsedData(null);
    setPhoto(null);
    setPreview('');
    setMessage('');
  };

  const handleAttack = async (dataToSubmit = null) => {
    setLoadingAction(true);
    setMessage('');

    const payload = dataToSubmit || formData;

    try {
      const result = await sendAttack(payload);
      setCurrentUser((prev) => ({
        ...prev,
        xp: prev.xp + result.xp_earned,
        gold: prev.gold + result.gold_earned,
      }));
      setMessage(`✅ ${result.message}`);
      await loadRaidData();
    } catch (e) {
      const errorText = e.message || 'Ошибка';
      const parts = errorText.split('\n\n📄 Распознанный текст:\n');
      const mainError = parts[0];
      const recognizedText = parts[1] || null;

      if (recognizedText) {
        setMessage({ type: 'error', main: mainError, rawText: recognizedText });
      } else {
        setMessage(`❌ ${mainError}`);
      }
    } finally {
      setLoadingAction(false);
    }
  };

  const setSport = (type) => {
    setFormData((prev) => ({ ...prev, sport_type: type }));
  };

  // --- SCREENS ---

  if (screen === 'loading') {
    return <div className="center-screen">Загрузка...</div>;
  }

  if (screen === 'auth') {
    return (
      <div className="container fade-in">
        <div className="card auth-card">
          <h1>Pulse Guardian</h1>
          <p className="auth-subtitle">
            {authMode === 'login' ? 'Вход в игру' : 'Создание героя'}
          </p>
          <form className="auth-form" onSubmit={handleAuthSubmit}>
            <label>
              Имя героя
              <input
                type="text"
                autoComplete="username"
                value={authForm.username}
                onChange={(e) =>
                  setAuthForm((prev) => ({ ...prev, username: e.target.value }))
                }
                placeholder="Например, DevHero"
              />
            </label>
            <label>
              Пароль
              <input
                type="password"
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                value={authForm.password}
                onChange={(e) =>
                  setAuthForm((prev) => ({ ...prev, password: e.target.value }))
                }
                placeholder="Минимум 4 символа"
              />
            </label>
            {authError && <div className="auth-error">{authError}</div>}
            <button className="attack-btn" type="submit" disabled={loadingAction}>
              {loadingAction
                ? '...'
                : authMode === 'login'
                  ? 'Войти'
                  : 'Зарегистрироваться'}
            </button>
          </form>
          <button
            type="button"
            className="auth-switch"
            onClick={() => {
              setAuthError('');
              setAuthMode((m) => (m === 'login' ? 'register' : 'login'));
            }}
          >
            {authMode === 'login'
              ? 'Нет аккаунта? Зарегистрироваться'
              : 'Уже есть аккаунт? Войти'}
          </button>
        </div>
      </div>
    );
  }

  if (screen === 'shop') {
    return (
      <div className="container fade-in">
        <div className="header-row">
          <button className="back-btn" onClick={() => setScreen('main')}>
            ← Назад
          </button>
          <div className="gold-info">💰 {currentUser.gold}</div>
        </div>
        <h1>🛒 Магазин</h1>
        <div className="shop-list">
          {shopItems.map((item) => (
            <div
              key={item.key}
              className={`shop-item ${item.is_locked ? 'locked' : ''} ${item.sport_type}`}
            >
              <div className="item-info">
                <h3>
                  {item.name}{' '}
                  {item.current_level > 0 && (
                    <span className="lvl-tag">Lvl {item.current_level}</span>
                  )}
                </h3>
                <p>{item.description}</p>
                {item.is_locked && (
                  <small className="lock-reason">🔒 Требуются улучшения 10 ур.</small>
                )}
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
    );
  }

  if (screen === 'rules') {
    return (
      <div className="container fade-in">
        <div className="card">
          <h1>📜 Кодекс</h1>
          <p>Привет, {currentUser.username}! Титан Лени угрожает нам.</p>
          <ul className="rules-list">
            <li>
              🏃 <b>Тренируйся:</b> Бег, Вело, Плаванье.
            </li>
            <li>
              🔥 <b>Сжигай:</b> Калории = Урон по боссу.
            </li>
            <li>
              💰 <b>Зарабатывай:</b> Золото делят победители.
            </li>
          </ul>
          <button className="attack-btn" onClick={handleEnterGame}>
            Вступить
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
          <button className="attack-btn" onClick={handleEnterGame}>
            В БОЙ ⚔️
          </button>
          <button type="button" className="auth-switch" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </div>
    );
  }

  if (!raid) {
    return <div className="center-screen">Поиск сигнала...</div>;
  }

  return (
    <div className="container main-layout">
      <header className="game-header">
        <div className="user-info">
          <span className="lvl-badge">{currentUser.level}</span>
          <span>{currentUser.username}</span>
        </div>
        <div className="header-actions">
          <div className="gold-info">💰 {currentUser.gold}</div>
          <button type="button" className="logout-btn" onClick={handleLogout} title="Выйти">
            ⎋
          </button>
        </div>
      </header>

      <button className="shop-btn-floating" onClick={openShop}>
        🛒
      </button>

      <div className="battle-arena">
        <div className={`boss-center ${raid.boss_type}`}>
          <div className="boss-emoji">👹</div>
        </div>
        {raid.participants?.map((p, index) => {
          const total = raid.participants.length;
          const angle = (index / total) * 2 * Math.PI;
          const x = Math.cos(angle - Math.PI / 2) * 100;
          const y = Math.sin(angle - Math.PI / 2) * 100;
          return (
            <div
              key={index}
              className="player-orbit"
              style={{ transform: `translate(${x}px, ${y}px)` }}
            >
              <div
                className="player-avatar"
                style={{ backgroundColor: p.avatar_color }}
              >
                {p.username.charAt(0).toUpperCase()}
              </div>
            </div>
          );
        })}
      </div>

      <div className="card boss-card">
        <h2 className="boss-name">{raid.boss_name}</h2>
        <div className="hp-wrapper">
          <div className="hp-container">
            <div
              className="hp-fill"
              style={{
                width: `${Math.max(0, (raid.current_hp / raid.max_hp) * 100)}%`,
              }}
            ></div>
          </div>
          <span className="hp-numbers">
            {raid.current_hp} / {raid.max_hp} HP
          </span>
        </div>
        {raid.active_debuffs?.armor_break && (
          <div className="debuff-notification">🔨 БРОНЯ РАСКОЛОТА!</div>
        )}
      </div>

      <div className="card action-card">
        {!showAttackForm ? (
          <button
            className="attack-btn primary"
            onClick={() => setShowAttackForm(true)}
          >
            ВНЕСТИ ТРЕНИРОВКУ 📷
          </button>
        ) : (
          <div className="attack-form fade-in">
            <h3>Тип тренировки</h3>
            <div className="sport-grid">
              <button
                className={`sport-btn ${formData.sport_type === 'run' ? 'active' : ''}`}
                onClick={() => setSport('run')}
              >
                🏃 Бег
              </button>
              <button
                className={`sport-btn ${formData.sport_type === 'cycle' ? 'active' : ''}`}
                onClick={() => setSport('cycle')}
              >
                🚴 Велосипед
              </button>
              <button
                className={`sport-btn ${formData.sport_type === 'swim' ? 'active' : ''}`}
                onClick={() => setSport('swim')}
              >
                🏊 Бассейн
              </button>
              <button
                className={`sport-btn ${formData.sport_type === 'football' ? 'active' : ''}`}
                onClick={() => setSport('football')}
              >
                ⚽ Футбол
              </button>
            </div>

            {!confirmMode ? (
              <>
                <label className="upload-label">
                  📎 Прикрепить фото
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const file = e.target.files[0];
                      if (file) {
                        setPhoto(file);
                        setPreview(URL.createObjectURL(file));
                        setParsedData(null);
                        setConfirmMode(false);
                        setMessage('');
                      }
                    }}
                    style={{ display: 'none' }}
                  />
                </label>
                {preview && (
                  <img
                    src={preview}
                    alt="Предпросмотр"
                    style={{
                      width: '100%',
                      borderRadius: '8px',
                      margin: '10px 0',
                    }}
                  />
                )}
                <button
                  className="attack-btn"
                  disabled={!photo || loadingAction}
                  onClick={handleParse}
                >
                  {loadingAction ? 'Распознаём...' : 'Распознать'}
                </button>
              </>
            ) : (
              <div className="parsed-preview">
                <h3>Подтверди данные:</h3>
                <ul>
                  {parsedData.distance_km > 0 && (
                    <li>📏 Дистанция: {parsedData.distance_km} км</li>
                  )}
                  {parsedData.duration_minutes > 0 && (
                    <li>⏱️ Время: {parsedData.duration_minutes} мин</li>
                  )}
                  {parsedData.calories > 0 && (
                    <li>🔥 Калории: {parsedData.calories} ккал</li>
                  )}
                  <li>
                    <strong>🎯 Вид спорта:</strong> {parsedData.sport_type}
                  </li>
                </ul>

                <details
                  style={{ fontSize: '0.8em', color: '#888', marginTop: '10px' }}
                >
                  <summary>📄 Показать распознанный текст</summary>
                  <pre
                    style={{
                      whiteSpace: 'pre-wrap',
                      background: '#111',
                      padding: '10px',
                      borderRadius: '6px',
                    }}
                  >
                    {parsedData.raw_text}
                  </pre>
                </details>

                <div className="form-actions">
                  <button className="cancel-btn" onClick={handleRetry}>
                    Перезагрузить
                  </button>
                  <button className="attack-btn" onClick={handleConfirm}>
                    ✅ Подтвердить
                  </button>
                </div>
              </div>
            )}

            {message && (
              <div className="game-message">
                {typeof message === 'object' ? (
                  <>
                    <div>❌ {message.main}</div>
                    {message.rawText && (
                      <details
                        style={{
                          fontSize: '0.75em',
                          color: '#aaa',
                          marginTop: '8px',
                        }}
                      >
                        <summary>📄 Показать распознанный текст</summary>
                        <pre
                          style={{
                            whiteSpace: 'pre-wrap',
                            background: '#111',
                            padding: '8px',
                            borderRadius: '4px',
                            marginTop: '5px',
                            maxHeight: '150px',
                            overflow: 'auto',
                          }}
                        >
                          {message.rawText}
                        </pre>
                      </details>
                    )}
                  </>
                ) : (
                  message
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="logs-container">
        {raid.recent_logs.map((log, i) => (
          <div key={i} className="log-item">
            <span className="log-user">{log.username}</span>
            <span className="log-action">
              {log.message ? (
                <>💬 {log.message}</>
              ) : (
                <>
                  нанес <span className="log-dmg">-{log.damage}</span>
                </>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
