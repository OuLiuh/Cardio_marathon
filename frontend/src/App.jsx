/**
 * App.jsx — Основной компонент React-приложения "Pulse Guardian"
 *
 * Отвечает за:
 * - Управление экранами (загрузка, правила, главное меню, магазин),
 * - Работу с Telegram WebApp,
 * - Загрузку и OCR-распознавание фото тренировки,
 * - Подтверждение данных перед отправкой,
 * - Взаимодействие с бэкендом через API.
 */

import { useState, useEffect } from 'react';
import { 
  fetchRaidState, 
  sendAttack, 
  getUser, 
  registerUser, 
  fetchShop, 
  buyItem,
  scanWorkout
} from './api';
import './App.css';

function App() {
  // --- СОСТОЯНИЕ ПРИЛОЖЕНИЯ ---
  /**
   * screen — текущий экран: 
   *   'loading'     → начальная загрузка
   *   'rules'       → правила игры (до регистрации)
   *   'welcome'     → приветствие после регистрации
   *   'main'        → основная арена битвы
   *   'shop'        → магазин улучшений
   */
  const [screen, setScreen] = useState('loading');

  /**
   * currentUser — данные авторизованного пользователя (id, уровень, золото и т.д.)
   */
  const [currentUser, setCurrentUser] = useState(null);

  /**
   * raid — текущее состояние рейда (босс, логи, участники)
   */
  const [raid, setRaid] = useState(null);

  /**
   * shopItems — список товаров из магазина с их статусом (уровень, цена, заблокировано)
   */
  const [shopItems, setShopItems] = useState([]);

  /**
   * tgData — данные пользователя из Telegram (id, имя)
   */
  const [tgData, setTgData] = useState({ id: null, first_name: 'Hero' });

  /**
   * showAttackForm — показывать ли форму ввода/загрузки тренировки
   */
  const [showAttackForm, setShowAttackForm] = useState(false);

  /**
   * loadingAction — индикатор выполнения запроса (кнопки становятся неактивными)
   */
  const [loadingAction, setLoadingAction] = useState(false);

  /**
   * message — временные сообщения пользователю (успех/ошибка)
   */
  const [message, setMessage] = useState('');

  // --- OCR-СВЯЗАННОЕ СОСТОЯНИЕ ---
  /**
   * photo — выбранный файл изображения
   */
  const [photo, setPhoto] = useState(null);

  /**
   * preview — URL для предпросмотра изображения
   */
  const [preview, setPreview] = useState('');

  /**
   * parsedData — распознанные данные с фото (дистанция, время, калории)
   */
  const [parsedData, setParsedData] = useState(null);

  /**
   * confirmMode — режим подтверждения: показываем ли результат OCR
   */
  const [confirmMode, setConfirmMode] = useState(false);

  /**
   * formData — текущие данные тренировки (используются при отправке)
   */
  const [formData, setFormData] = useState({
    sport_type: 'run',
    duration_minutes: 30,
    calories: 0,
    distance_km: 0.0,
    avg_heart_rate: 0
  });

  // --- ИНИЦИАЛИЗАЦИЯ: ЗАГРУЗКА ДАННЫХ ПРИ ЗАПУСКЕ ---
  /**
   * При первом рендере:
   * - Получает данные пользователя из Telegram WebApp,
   * - Если нет — использует тестовые,
   * - Проверяет, зарегистрирован ли пользователь.
   */
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

  // --- АВТООБНОВЛЕНИЕ РЕЙДА ---
  /**
   * При входе на экран 'main':
   * - Загружает состояние рейда,
   * - Обновляет каждые 3 секунды,
   * - Очищает интервал при выходе.
   */
  useEffect(() => {
    if (screen === 'main') {
      loadRaidData();
      const interval = setInterval(loadRaidData, 3000);
      return () => clearInterval(interval);
    }
  }, [screen]);

  // --- ПРОВЕРКА СТАТУСА ПОЛЬЗОВАТЕЛЯ ---
  /**
   * Проверяет, существует ли пользователь в БД.
   * Если да — переходит на экран приветствия.
   * Если нет — просит принять правила и зарегистрироваться.
   */
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

  // --- ЗАГРУЗКА ДАННЫХ РЕЙДА ---
  /**
   * Запрашивает текущее состояние босса и игроков.
   * Обновляет локальное состояние `raid`.
   */
  const loadRaidData = async () => {
    const data = await fetchRaidState();
    if (data) setRaid(data);
  };

  // --- ОТКРЫТИЕ МАГАЗИНА ---
  /**
   * Переходит в экран магазина.
   * Загружает список доступных улучшений.
   */
  const openShop = async () => {
    haptic('selection');
    setLoadingAction(true);
    try {
      const items = await fetchShop(currentUser.id);
      setShopItems(items);
      setScreen('shop');
    } catch (e) {
      alert("Ошибка магазина");
    } finally {
      setLoadingAction(false);
    }
  };

  // --- ПОКУПКА В МАГАЗИНЕ ---
  /**
   * Отправляет запрос на покупку улучшения.
   * Обновляет баланс золота и список товаров.
   */
  const handleBuy = async (itemKey) => {
    haptic('selection');
    try {
      const res = await buyItem(currentUser.id, itemKey);
      setCurrentUser(prev => ({ ...prev, gold: res.gold_left }));
      const items = await fetchShop(currentUser.id);
      setShopItems(items);
      haptic('notification');
    } catch (e) {
      alert("Ошибка: " + e.message);
      haptic('impact');
    }
  };

  // --- РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
  /**
   * Отправляет имя и ID пользователя в БД.
   * После успешной регистрации переходит в игру.
   */
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

  // --- ВХОД В ИГРУ ---
  /**
   * Переход с экрана приветствия в основную арену.
   */
  const handleEnterGame = () => {
    haptic('selection');
    setScreen('main');
  };

  // --- РАСПОЗНАВАНИЕ ФОТО ТРЕНИРОВКИ ---
  /**
   * Отправляет фото на сервер для OCR-анализа.
   * Получает распознанные данные: дистанция, время, калории.
   * Переключается в режим подтверждения.
   */
  const handleParse = async () => {
    if (!photo) return;
    setLoadingAction(true);
    setMessage('');
    
    const formDataObj = new FormData();
    formDataObj.append('file', photo);
    formDataObj.append('user_id', currentUser.id);
    formDataObj.append('sport_type', formData.sport_type);

    try {
      const result = await scanWorkout(formDataObj);
      setParsedData(result);
      setConfirmMode(true);
    } catch (e) {
      // Парсим сообщение об ошибке: если есть распознанный текст, показываем его отдельно
      const errorText = e.message || 'Ошибка';
      const parts = errorText.split('\n\n📄 Распознанный текст:\n');
      const mainError = parts[0];
      const recognizedText = parts[1] || null;
      
      if (recognizedText) {
        setMessage({
          type: 'error',
          main: mainError,
          rawText: recognizedText
        });
      } else {
        setMessage(`❌ ${mainError}`);
      }
    } finally {
      setLoadingAction(false);
    }
  };

  // --- ПОДТВЕРЖДЕНИЕ ДАННЫХ ---
  /**
   * Пользователь подтвердил распознанные данные.
   * Данные копируются в `formData` и отправляются как атака.
   */
  const handleConfirm = () => {
    haptic('notification');
    const { raw_text, ...safeData } = parsedData;

    // Стейт всё равно обновим (на всякий случай, если он нужен для UI)
    setFormData(prev => ({ ...prev, ...safeData }));
    setShowAttackForm(false);

    // Отправляем правильные данные СРАЗУ
    handleAttack(safeData);
  };

  // --- ПОВТОРНАЯ ЗАГРУЗКА ФОТО ---
  /**
   * Сброс всех данных OCR, чтобы загрузить новое фото.
   */
  const handleRetry = () => {
    setConfirmMode(false);
    setParsedData(null);
    setPhoto(null);
    setPreview('');
    setMessage('');
  };

  // --- ОТПРАВКА АТАКИ (ТРЕНИРОВКИ) ---
  /**
   * Отправляет данные тренировки на сервер.
   * Обновляет XP, золото, HP босса.
   */
  const handleAttack = async (dataToSubmit = null) => {
    haptic('notification');
    setLoadingAction(true);
    setMessage('');

    // Если данные передали напрямую — используем их. Иначе берём из стейта.
    const payload = dataToSubmit || formData;

    try {
      const result = await sendAttack({ user_id: currentUser.id, ...payload });
      setCurrentUser(prev => ({
        ...prev,
        xp: prev.xp + result.xp_earned,
        gold: prev.gold + result.gold_earned
      }));
      setMessage(`✅ ${result.message}`);
      await loadRaidData();
    } catch (e) {
      // Парсим сообщение об ошибке: если есть распознанный текст, показываем его отдельно
      const errorText = e.message || 'Ошибка';
      const parts = errorText.split('\n\n📄 Распознанный текст:\n');
      const mainError = parts[0];
      const recognizedText = parts[1] || null;
      
      if (recognizedText) {
        setMessage({
          type: 'error',
          main: mainError,
          rawText: recognizedText
        });
      } else {
        setMessage(`❌ ${mainError}`);
      }
    } finally {
      setLoadingAction(false);
    }
  };

  // --- HAPTIC FEEDBACK (вибрация в Telegram) ---
  /**
   * Вызов тактильной обратной связи в Telegram WebApp.
   * Улучшает UX: клики, ошибки, успех.
   */
  const haptic = (type) => {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'impact') window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
      if (type === 'notification') window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      if (type === 'selection') window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
  };

  // --- ОБНОВЛЕНИЕ ПОЛЕЙ ФОРМЫ ---
  /**
   * Обновляет `formData` при изменении полей.
   * Преобразует строки в числа, кроме `sport_type`.
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ 
      ...prev, 
      [name]: name === 'sport_type' ? value : Number(value) 
    }));
  };

  // --- ВЫБОР ТИПА ТРЕНИРОВКИ ---
  /**
   * Устанавливает тип спорта и вызывает тактильную обратную связь.
   */
  const setSport = (type) => {
    setFormData(prev => ({ ...prev, sport_type: type }));
    haptic('selection');
  };

  // --- RENDER: ЭКРАНЫ ПРИЛОЖЕНИЯ ---

  if (screen === 'loading') {
    return <div className="center-screen">Загрузка данных...</div>;
  }

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
    );
  }

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
          <button className="attack-btn" onClick={handleRegister} disabled={loadingAction}>
            {loadingAction ? "..." : "Вступить"}
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
          <button className="attack-btn" onClick={handleEnterGame}>В БОЙ ⚔️</button>
        </div>
      </div>
    );
  }

  if (!raid) {
    return <div className="center-screen">Поиск сигнала...</div>;
  }

  // --- ОСНОВНОЙ ИНТЕРФЕЙС ИГРЫ ---
  return (
    <div className="container main-layout">
      {/* Шапка с ником и уровнем */}
      <header className="game-header">
        <div className="user-info">
          <span className="lvl-badge">{currentUser.level}</span>
          <span>{currentUser.username}</span>
        </div>
        <div className="gold-info">💰 {currentUser.gold}</div>
      </header>

      {/* Кнопка магазина */}
      <button className="shop-btn-floating" onClick={openShop}>🛒</button>

      {/* Арена битвы с боссом и игроками */}
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
            <div key={index} className="player-orbit" style={{ transform: `translate(${x}px, ${y}px)` }}>
              <div className="player-avatar" style={{ backgroundColor: p.avatar_color }}>
                {p.username.charAt(0).toUpperCase()}
              </div>
            </div>
          );
        })}
      </div>

      {/* Карточка босса: HP, имя, эффекты */}
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

      {/* Форма внесения тренировки */}
      <div className="card action-card">
        {!showAttackForm ? (
          <button className="attack-btn primary" onClick={() => setShowAttackForm(true)}>
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

            {/* Режим загрузки фото */}
            {!confirmMode ? (
              <>
                <label className="upload-label">
                  📎 Прикрепить фото
                  <input type="file" accept="image/*" onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                      setPhoto(file);
                      setPreview(URL.createObjectURL(file));
                      setParsedData(null);
                      setConfirmMode(false);
                      setMessage("");
                    }
                  }} style={{ display: "none" }} />
                </label>
                {preview && <img src={preview} alt="Предпросмотр" style={{ width: "100%", borderRadius: "8px", margin: "10px 0" }} />}
                <button className="attack-btn" disabled={!photo || loadingAction} onClick={handleParse}>
                  {loadingAction ? "Распознаём..." : "Распознать"}
                </button>
              </>
            ) : (
              /* Режим подтверждения данных */
              <div className="parsed-preview">
                <h3>Подтверди данные:</h3>
                <ul>
                  {parsedData.distance_km > 0 && <li>📏 Дистанция: {parsedData.distance_km} км</li>}
                  {parsedData.duration_minutes > 0 && <li>⏱️ Время: {parsedData.duration_minutes} мин</li>}
                  {parsedData.calories > 0 && <li>🔥 Калории: {parsedData.calories} ккал</li>}
                  <li><strong>🎯 Вид спорта:</strong> {parsedData.sport_type}</li>
                </ul>

                {/* Отладка: сырой текст OCR */}
                <details style={{ fontSize: '0.8em', color: '#888', marginTop: '10px' }}>
                  <summary>📄 Показать распознанный текст</summary>
                  <pre style={{ whiteSpace: 'pre-wrap', background: '#111', padding: '10px', borderRadius: '6px' }}>
                    {parsedData.raw_text}
                  </pre>
                </details>

                <div className="form-actions">
                  <button className="cancel-btn" onClick={handleRetry}>Перезагрузить</button>
                  <button className="attack-btn" onClick={handleConfirm}>✅ Подтвердить</button>
                </div>
              </div>
            )}

            {message && (
              <div className="game-message">
                {typeof message === 'object' ? (
                  <>
                    <div>❌ {message.main}</div>
                    {message.rawText && (
                      <details style={{ fontSize: '0.75em', color: '#aaa', marginTop: '8px' }}>
                        <summary>📄 Показать распознанный текст</summary>
                        <pre style={{ whiteSpace: 'pre-wrap', background: '#111', padding: '8px', borderRadius: '4px', marginTop: '5px', maxHeight: '150px', overflow: 'auto' }}>
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

      {/* Логи последних атак */}
      <div className="logs-container">
        {raid.recent_logs.map((log, i) => (
          <div key={i} className="log-item">
            <span className="log-user">{log.username}</span>
            <span className="log-action">
              {log.message ? (
                <>💬 {log.message}</>
              ) : (
                <>нанес <span className="log-dmg">-{log.damage}</span></>
              )}
            </span>
            {log.message && !log.damage && <br />}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;