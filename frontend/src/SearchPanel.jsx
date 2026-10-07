import { useEffect, useRef, useState } from 'react';
import { searchRequest, SESSION_EXPIRED } from './auth.js';
import './search.css';

export function searchHash(query, page = 1) {
  const params = new URLSearchParams({ q: query.trim(), page: String(page) });
  return `search?${params}`;
}

const kinds = { CLASSROOM: 'Учебный кабинет', STAFF_OFFICE: 'Кабинет сотрудника',
  BARREL: 'Лекционная аудитория', UNKNOWN: 'Тип помещения пока не уточнён' };
const statuses = { USER_REPORTED: 'По информации команды',
  PROVISIONAL: 'Предварительная рекомендация — требует проверки',
  UNKNOWN: 'Статус рекомендации пока не уточнён' };

function Result({ item }) {
  const room = item.type === 'room';
  const title = room
    ? (item.kind === 'BARREL' ? `${item.name} — ${item.code}` : `Кабинет ${item.code}`)
    : item.name;
  return <li className="search-result">
    <article aria-label={title}>
      <h2>{title}</h2>
      <p className="search-location">Блок {item.block.code}{room && ` · ${item.floor === 0 ? 'Подвал' : `${item.floor}-й этаж`}`}</p>
      {room && item.name && item.name !== `Кабинет ${item.code}` && item.kind !== 'BARREL' && <p>{item.name}</p>}
      {room && <p>{kinds[item.kind] || kinds.UNKNOWN}</p>}
      <p><strong>Рекомендуемый вход: </strong>{item.entrance.name || 'пока не указан'}</p>
      <p className="search-note">{statuses[item.entrance.status] || statuses.UNKNOWN}</p>
      {item.entrance.note && <p className="search-note">{item.entrance.note}</p>}
      {item.description && item.description !== item.entrance.note && <p>{item.description}</p>}
      {item.provisional && <p className="search-badge">Предварительные данные — требуют проверки</p>}
      {item.source && <p className="search-note">Источник: {item.source}</p>}
    </article>
  </li>;
}

export default function SearchPanel({ hash, onSignedOut }) {
  const params = new URLSearchParams(hash.split('?')[1] || '');
  const query = params.get('q') || '';
  const page = params.get('page') || '1';
  const [draft, setDraft] = useState(query);
  const [state, setState] = useState({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus(); }, [query, page]);
  useEffect(() => { setDraft(query); }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    if (!query.trim()) { setState({ status: 'empty' }); return () => controller.abort(); }
    setState({ status: 'loading' });
    searchRequest(query, page, { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) { onSignedOut(SESSION_EXPIRED); return; }
      if (!response.ok) throw new Error(data.detail || 'Не удалось выполнить поиск.');
      if (!Array.isArray(data.results)) throw new Error('Некорректный ответ сервера.');
      setState({ status: 'ready', data });
    }).catch((error) => {
      if (!controller.signal.aborted) setState({ status: 'error', message: error.message });
    });
    return () => controller.abort();
  }, [query, page, attempt, onSignedOut]);
  function submit(event) {
    event.preventDefault();
    const next = `#${searchHash(draft)}`;
    if (window.location.hash === next) setAttempt(value => value + 1);
    else window.location.hash = next;
  }
  return <section className="panel home-panel search-panel" lang="ru" aria-labelledby="search-title">
    <p className="eyebrow">Campus search</p>
    <h1 id="search-title" ref={heading} tabIndex="-1">Поиск кабинета или блока</h1>
    <form className="home-search" role="search" onSubmit={submit}>
      <label className="sr-only" htmlFor="room-query">Кабинет, блок или название помещения</label>
      <input id="room-query" type="search" maxLength={80} value={draft}
        onChange={event => setDraft(event.target.value)} placeholder="E204, Бочка A1, Блок E" autoComplete="off" />
      <button className="submit-button" type="submit">Search</button>
    </form>
    <div aria-live="polite" aria-busy={state.status === 'loading'}>
      {state.status === 'empty' && <p>Введите номер кабинета, блок или название: например, E204 или Бочка A1.</p>}
      {state.status === 'loading' && <p role="status">Ищем помещения…</p>}
      {state.status === 'error' && <div role="alert"><p>Не удалось выполнить поиск. {state.message}</p>
        <button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Повторить запрос</button></div>}
      {state.status === 'ready' && <>
        <p role="status">{state.data.count ? `Найдено: ${state.data.count}` : 'Ничего не найдено. Проверьте номер или попробуйте название блока.'}</p>
        <ul className="search-results">{state.data.results.map(item => <Result key={`${item.type}-${item.id}`} item={item} />)}</ul>
        {(Number(page) > 1 || state.data.next_page) && <nav className="search-pagination" aria-label="Страницы результатов">
          {Number(page) > 1 && <a href={`#${searchHash(query, Number(page) - 1)}`}>← Назад</a>}
          <span>Страница {state.data.page}</span>
          {state.data.next_page && <a href={`#${searchHash(query, state.data.next_page)}`}>Далее →</a>}
        </nav>}
      </>}
    </div>
    <div className="panel-footer home-footer"><a className="home-profile-link" href="#home">← На главную</a></div>
  </section>;
}
