/**
 * App.jsx — Pulse Guardian (zombie apocalypse UI)
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

const BOSS_META = {
  normal: {
    label: 'Обычный',
    icon: '🧟',
    className: 'type-normal',
    short: 'Без особых способностей',
    detail: 'Стандартный босс. Урон проходит без штрафов и уворотов.',
  },
  armored: {
    label: 'Бронированный',
    icon: '🛡️',
    className: 'type-armored',
    short: '−50% урона, пока броня цела',
    detail:
      'Снижает весь урон на 50%, пока броня не расколота. Плавание и футбол имеют 30% шанс пробить броню. После пробития урон ×1.15. HP на 10% выше обычного.',
  },
  agile: {
    label: 'Ловкий',
    icon: '💨',
    className: 'type-agile',
    short: '20% шанс полностью увернуться',
    detail:
      'Перед расчётом урона бросается шанс 20%: при успехе атака — промах (0 урона).',
  },
  radioactive: {
    label: 'Радиоактивный',
    icon: '☢️',
    className: 'type-radioactive',
    short: 'Реген 5% HP в сутки',
    detail:
      'Каждые сутки восстанавливает 5% от максимального HP. Нужно бить чаще, иначе босс «отрастает».',
  },
  swarm: {
    label: 'Рой',
    icon: '👾',
    className: 'type-swarm',
    short: '−20% HP, стая мелких',
    detail:
      'Визуально — рой. Механически: на 20% меньше HP, без особых трейтов. Быстрее падает, но и наградный пул скромнее.',
  },
};

const ACTIVITY_INFO = [
  {
    key: 'run',
    label: 'Бег',
    icon: '🏃',
    short: 'Дистанция × 75 + время',
    detail:
      'Урон = (км × 75) + минуты. Если время < 30 мин — урон ×0.8. Если дистанция > 5 км — урон ×1.1. Затем множитель уровня героя (+1% за уровень) и апгрейды.',
  },
  {
    key: 'cycle',
    label: 'Велосипед',
    icon: '🚴',
    short: '30 × км + время',
    detail:
      'Урон = (30 × км) + минуты. Затем множитель уровня (+1% за ур.) и апгрейды магазина.',
  },
  {
    key: 'swim',
    label: 'Плавание',
    icon: '🏊',
    short: 'Метры / 2, шанс пробить броню',
    detail:
      'Урон = (км × 1000) / 2, то есть метры ÷ 2. 30% шанс наложить «броня расколота». Затем уровень и апгрейды.',
  },
  {
    key: 'football',
    label: 'Футбол',
    icon: '⚽',
    short: 'Калории / 2, шанс пробить броню',
    detail:
      'Урон = калории ÷ 2. 30% шанс пробить броню босса. Затем уровень и апгрейды.',
  },
];

const SPORT_OPTIONS = ACTIVITY_INFO.map(({ key, label, icon }) => ({
  key,
  label: key === 'cycle' ? 'Вело' : key === 'swim' ? 'Бассейн' : label,
  icon,
}));

function getBossMeta(type) {
  return BOSS_META[type] || BOSS_META.normal;
}

function IconShop() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M4 7h16l-1.2 12.2A2 2 0 0 1 16.81 21H7.19a2 2 0 0 1-1.99-1.8L4 7zm3-4h10l1 3H6l1-3z"
      />
    </svg>
  );
}

function IconLogout() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M10 3h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-8v-2h8V5h-8V3zm-1.3 5.3 1.4-1.4L15.2 12l-5.1 5.1-1.4-1.4L11.4 13H3v-2h8.4L8.7 8.3z"
      />
    </svg>
  );
}

function IconUser() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 12a4.5 4.5 0 1 0-4.5-4.5A4.5 4.5 0 0 0 12 12zm0 2c-4.2 0-8 2.1-8 5v1h16v-1c0-2.9-3.8-5-8-5z"
      />
    </svg>
  );
}

function IconBack() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M14.7 5.3 8 12l6.7 6.7 1.4-1.4L10.8 12l5.3-5.3-1.4-1.4z"
      />
    </svg>
  );
}

function IconGold() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2a7 7 0 0 0-7 7c0 4.2 3.3 7.6 7.5 11.1L12 22l-.5-1.9C15.7 16.6 19 13.2 19 9a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 14.5 9 2.5 2.5 0 0 1 12 11.5z"
      />
    </svg>
  );
}

function IconInfo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 4.2a1.4 1.4 0 1 1-1.4 1.4A1.4 1.4 0 0 1 12 6.2zM13.2 17h-2.4v-7h2.4z"
      />
    </svg>
  );
}

function CodexPanel({ mode, onSelect }) {
  if (mode === 'menu') {
    return (
      <div className="codex-menu fade-in">
        <h2 className="codex-title">Справочник выжившего</h2>
        <p className="codex-lede">Выбери раздел</p>
        <button type="button" className="btn btn-primary" onClick={() => onSelect('activities')}>
          Активности и урон
        </button>
        <button type="button" className="btn btn-ghost codex-second-btn" onClick={() => onSelect('bosses')}>
          Типы боссов
        </button>
      </div>
    );
  }

  if (mode === 'activities') {
    return (
      <div className="codex-detail fade-in">
        <button type="button" className="btn btn-ghost btn-sm codex-back" onClick={() => onSelect('menu')}>
          ← К разделам
        </button>
        <h2 className="codex-title">Активности</h2>
        <p className="codex-lede">
          Базовый урон считается по формуле вида спорта, затем × (1 + уровень × 0.01) и апгрейды.
          Броня босса может резать урон вдвое, пока не пробита.
        </p>
        <ul className="codex-list">
          {ACTIVITY_INFO.map((a) => (
            <li key={a.key}>
              <span className="codex-icon">{a.icon}</span>
              <div>
                <strong>{a.label}</strong>
                <span className="codex-formula">{a.short}</span>
                <span>{a.detail}</span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="codex-detail fade-in">
      <button type="button" className="btn btn-ghost btn-sm codex-back" onClick={() => onSelect('menu')}>
        ← К разделам
      </button>
      <h2 className="codex-title">Типы боссов</h2>
      <p className="codex-lede">Тип выбирается случайно при старте рейда.</p>
      <ul className="codex-list">
        {Object.entries(BOSS_META).map(([key, b]) => (
          <li key={key}>
            <span className="codex-icon">{b.icon}</span>
            <div>
              <strong className={b.className}>{b.label}</strong>
              <span className="codex-formula">{b.short}</span>
              <span>{b.detail}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MessageBlock({ message }) {
  if (!message) return null;
  const isError = typeof message === 'object' || String(message).startsWith('❌');
  return (
    <div className={`game-message ${isError ? 'is-error' : 'is-ok'}`}>
      {typeof message === 'object' ? (
        <>
          <div>{message.main}</div>
          {message.rawText && (
            <details className="raw-details">
              <summary>Распознанный текст</summary>
              <pre>{message.rawText}</pre>
            </details>
          )}
        </>
      ) : (
        message
      )}
    </div>
  );
}

function App() {
  const [screen, setScreen] = useState('loading');
  const [authMode, setAuthMode] = useState('login');
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
  const [shopInfoOpen, setShopInfoOpen] = useState(false);
  const [codexView, setCodexView] = useState('menu'); // menu | activities | bosses
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

  const bossMeta = raid ? getBossMeta(raid.boss_type) : null;
  const hpPercent = raid
    ? Math.max(0, Math.min(100, (raid.current_hp / raid.max_hp) * 100))
    : 0;

  if (screen === 'loading') {
    return (
      <div className="app-shell">
        <div className="center-screen">
          <div className="pulse-loader" />
          <p>Сканирование зоны...</p>
        </div>
      </div>
    );
  }

  if (screen === 'auth') {
    return (
      <div className="app-shell">
        <div className="atmosphere" aria-hidden="true" />
        <div className="container fade-in auth-screen">
          <div className="brand-block">
            <p className="brand-mark">Pulse Guardian</p>
            <p className="brand-tagline">Выживи. Тренируйся. Убей босса.</p>
          </div>

          <form className="panel auth-panel" onSubmit={handleAuthSubmit}>
            <div className="auth-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                className={`auth-tab ${authMode === 'login' ? 'active' : ''}`}
                aria-selected={authMode === 'login'}
                onClick={() => {
                  setAuthError('');
                  setAuthMode('login');
                }}
              >
                <IconUser />
                <span>Вход</span>
              </button>
              <button
                type="button"
                role="tab"
                className={`auth-tab ${authMode === 'register' ? 'active' : ''}`}
                aria-selected={authMode === 'register'}
                onClick={() => {
                  setAuthError('');
                  setAuthMode('register');
                }}
              >
                <IconUser />
                <span>Регистрация</span>
              </button>
            </div>

            <label className="field">
              <span>Имя героя</span>
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
            <label className="field">
              <span>Пароль</span>
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

            <button className="btn btn-primary" type="submit" disabled={loadingAction}>
              {loadingAction
                ? '...'
                : authMode === 'login'
                  ? 'Войти в зону'
                  : 'Создать героя'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (screen === 'shop') {
    return (
      <div className="app-shell">
        <div className="atmosphere" aria-hidden="true" />
        <div className="container fade-in">
          <header className="top-bar">
            <div className="top-side">
              <button className="icon-btn" onClick={() => setScreen('main')} title="Назад">
                <IconBack />
              </button>
            </div>
            <h1 className="screen-title">Арсенал</h1>
            <div className="top-side top-side-end">
              <button
                type="button"
                className="icon-btn"
                title="Справка"
                onClick={() => {
                  setCodexView('menu');
                  setShopInfoOpen(true);
                }}
              >
                <IconInfo />
              </button>
              <div className="gold-chip" title="Золото">
                <IconGold />
                <span>{currentUser.gold}</span>
              </div>
            </div>
          </header>

          <div className="shop-list">
            {shopItems.map((item) => (
              <div
                key={item.key}
                className={`shop-item ${item.is_locked ? 'locked' : ''} ${item.sport_type}`}
              >
                <div className="item-info">
                  <h3>
                    {item.name}
                    {item.current_level > 0 && (
                      <span className="lvl-tag">Lvl {item.current_level}</span>
                    )}
                  </h3>
                  <p>{item.description}</p>
                  {item.is_locked && (
                    <small className="lock-reason">Требуются улучшения 10 ур.</small>
                  )}
                </div>
                <div className="item-action">
                  {item.is_maxed ? (
                    <span className="max-tag">MAX</span>
                  ) : (
                    <button
                      className="btn btn-buy"
                      disabled={item.is_locked || currentUser.gold < item.next_price}
                      onClick={() => handleBuy(item.key)}
                    >
                      <IconGold />
                      {item.next_price}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {shopInfoOpen && (
            <div
              className="modal-backdrop"
              role="dialog"
              aria-modal="true"
              aria-label="Справка"
              onClick={(e) => {
                if (e.target === e.currentTarget) setShopInfoOpen(false);
              }}
            >
              <div className="modal-panel">
                <button
                  type="button"
                  className="modal-close"
                  onClick={() => setShopInfoOpen(false)}
                  title="Закрыть"
                >
                  ×
                </button>
                <CodexPanel mode={codexView} onSelect={setCodexView} />
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (screen === 'rules') {
    return (
      <div className="app-shell">
        <div className="atmosphere" aria-hidden="true" />
        <div className="container fade-in">
          <div className="panel rules-panel">
            <p className="brand-mark brand-mark-sm">Pulse Guardian</p>
            <h1 className="screen-title">Кодекс выживания</h1>
            <p className="lede">
              Привет, {currentUser.username}. Титан Лени уже в городе — держись в строю.
            </p>
            <ul className="rules-list">
              <li>
                <span className="rule-icon">🏃</span>
                <div>
                  <strong>Тренируйся</strong>
                  <span>Бег, вело, плаванье, футбол</span>
                </div>
              </li>
              <li>
                <span className="rule-icon">🔥</span>
                <div>
                  <strong>Сжигай</strong>
                  <span>Калории превращаются в урон по боссу</span>
                </div>
              </li>
              <li>
                <span className="rule-icon">💰</span>
                <div>
                  <strong>Зарабатывай</strong>
                  <span>Золото делят победители рейда</span>
                </div>
              </li>
            </ul>
            <button className="btn btn-primary" onClick={handleEnterGame}>
              Вступить в рейд
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (screen === 'welcome') {
    return (
      <div className="app-shell">
        <div className="atmosphere" aria-hidden="true" />
        <div className="container fade-in">
          <div className="panel welcome-panel">
            <p className="brand-mark">Pulse Guardian</p>
            <h1 className="welcome-name">{currentUser.username}</h1>
            <p className="lede">Готов к вылазке? Краткий брифинг перед боем.</p>
            <div className="stats-row">
              <div className="stat-chip">Lv. {currentUser.level}</div>
              <div className="stat-chip gold">
                <IconGold />
                {currentUser.gold}
              </div>
            </div>

            <section className="brief-block">
              <h2 className="brief-title">Активности</h2>
              <ul className="brief-list">
                {ACTIVITY_INFO.map((a) => (
                  <li key={a.key}>
                    <span>{a.icon}</span>
                    <div>
                      <strong>{a.label}</strong>
                      <span>{a.short}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section className="brief-block">
              <h2 className="brief-title">Боссы</h2>
              <ul className="brief-list">
                {Object.entries(BOSS_META).map(([key, b]) => (
                  <li key={key}>
                    <span>{b.icon}</span>
                    <div>
                      <strong>{b.label}</strong>
                      <span>{b.short}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <button className="btn btn-primary" onClick={handleEnterGame}>
              В бой
            </button>
            <button type="button" className="btn btn-ghost" onClick={handleLogout}>
              Выйти
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!raid) {
    return (
      <div className="app-shell">
        <div className="center-screen">
          <div className="pulse-loader" />
          <p>Поиск сигнала рейда...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="atmosphere" aria-hidden="true" />
      <div className="container main-layout fade-in">
        <header className="top-bar">
          <div className="user-chip">
            <span className="lvl-badge">Lv.{currentUser.level}</span>
            <span className="user-name">{currentUser.username}</span>
          </div>

          <nav className="icon-rail" aria-label="Действия">
            <div className="gold-chip" title="Золото">
              <IconGold />
              <span>{currentUser.gold}</span>
            </div>
            <button
              type="button"
              className="icon-btn"
              onClick={openShop}
              title="Магазин"
              disabled={loadingAction}
            >
              <IconShop />
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={handleLogout}
              title="Выйти"
            >
              <IconLogout />
            </button>
          </nav>
        </header>

        <section className="battle-arena" aria-label="Арена рейда">
          <div className="orbit-ring" aria-hidden="true" />
          <div className={`boss-center ${raid.boss_type}`}>
            <div className="boss-emoji" aria-hidden="true">
              {bossMeta.icon}
            </div>
            <div className={`boss-type-pill ${bossMeta.className}`}>
              {bossMeta.label}
            </div>
            <div className="boss-hp-mini">
              <div className="boss-hp-mini-fill" style={{ width: `${hpPercent}%` }} />
            </div>
          </div>

          {raid.participants?.map((p, index) => {
            const total = Math.max(raid.participants.length, 1);
            const angle = (index / total) * 2 * Math.PI;
            const radius = 118;
            const x = Math.cos(angle - Math.PI / 2) * radius;
            const y = Math.sin(angle - Math.PI / 2) * radius;
            return (
              <div
                key={`${p.username}-${index}`}
                className="player-orbit"
                style={{
                  transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
                }}
                title={p.username}
              >
                <div
                  className="player-avatar"
                  style={{ backgroundColor: p.avatar_color }}
                >
                  {p.username.charAt(0).toUpperCase()}
                </div>
                <span className="player-label">{p.username}</span>
              </div>
            );
          })}
        </section>

        <section className="boss-hud">
          <div className="boss-hud-top">
            <h2 className="boss-name">{raid.boss_name}</h2>
            <span className={`boss-type-badge ${bossMeta.className}`}>
              {bossMeta.icon} {bossMeta.label}
            </span>
          </div>
          <div className="hp-wrapper">
            <div className="hp-container" role="progressbar" aria-valuenow={raid.current_hp} aria-valuemin={0} aria-valuemax={raid.max_hp}>
              <div className="hp-fill" style={{ width: `${hpPercent}%` }} />
            </div>
            <span className="hp-numbers">
              {raid.current_hp} / {raid.max_hp} HP
            </span>
          </div>
          {raid.active_debuffs?.armor_break && (
            <div className="debuff-notification">Броня расколота</div>
          )}
        </section>

        <section className="action-panel">
          {!showAttackForm ? (
            <button
              className="btn btn-primary btn-xl"
              onClick={() => setShowAttackForm(true)}
            >
              Внести тренировку
            </button>
          ) : (
            <div className="attack-form fade-in">
              <div className="form-head">
                <h3>Тип тренировки</h3>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setShowAttackForm(false);
                    handleRetry();
                  }}
                >
                  Закрыть
                </button>
              </div>

              <div className="sport-grid">
                {SPORT_OPTIONS.map((sport) => (
                  <button
                    key={sport.key}
                    type="button"
                    className={`sport-btn ${formData.sport_type === sport.key ? 'active' : ''}`}
                    onClick={() => setSport(sport.key)}
                  >
                    <span className="sport-icon">{sport.icon}</span>
                    <span>{sport.label}</span>
                  </button>
                ))}
              </div>

              {!confirmMode ? (
                <>
                  <label className="upload-label">
                    <span className="upload-title">Прикрепить фото</span>
                    <span className="upload-hint">Скриншот тренировки</span>
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
                    />
                  </label>
                  {preview && (
                    <img src={preview} alt="Предпросмотр" className="preview-img" />
                  )}
                  <button
                    className="btn btn-primary"
                    disabled={!photo || loadingAction}
                    onClick={handleParse}
                  >
                    {loadingAction ? 'Распознаём...' : 'Распознать'}
                  </button>
                </>
              ) : (
                <div className="parsed-preview">
                  <h3>Подтверди данные</h3>
                  <ul className="parsed-list">
                    {parsedData.distance_km > 0 && (
                      <li>
                        <span>Дистанция</span>
                        <strong>{parsedData.distance_km} км</strong>
                      </li>
                    )}
                    {parsedData.duration_minutes > 0 && (
                      <li>
                        <span>Время</span>
                        <strong>{parsedData.duration_minutes} мин</strong>
                      </li>
                    )}
                    {parsedData.calories > 0 && (
                      <li>
                        <span>Калории</span>
                        <strong>{parsedData.calories} ккал</strong>
                      </li>
                    )}
                    <li>
                      <span>Вид спорта</span>
                      <strong>{parsedData.sport_type}</strong>
                    </li>
                  </ul>

                  {parsedData.raw_text && (
                    <details className="raw-details">
                      <summary>Распознанный текст</summary>
                      <pre>{parsedData.raw_text}</pre>
                    </details>
                  )}

                  <div className="form-actions">
                    <button className="btn btn-ghost" onClick={handleRetry}>
                      Заново
                    </button>
                    <button className="btn btn-primary" onClick={handleConfirm}>
                      Подтвердить удар
                    </button>
                  </div>
                </div>
              )}

              <MessageBlock message={message} />
            </div>
          )}

          {!showAttackForm && <MessageBlock message={message} />}
        </section>

        <section className="logs-container" aria-label="Журнал боя">
          <h3 className="logs-title">Журнал боя</h3>
          {raid.recent_logs?.length ? (
            raid.recent_logs.map((log, i) => (
              <div key={i} className="log-item">
                <span className="log-user">{log.username}</span>
                <span className="log-action">
                  {log.message ? (
                    log.message
                  ) : (
                    <>
                      нанёс <span className="log-dmg">-{log.damage}</span>
                    </>
                  )}
                </span>
              </div>
            ))
          ) : (
            <p className="logs-empty">Пока тихо. Первый удар за тобой.</p>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
