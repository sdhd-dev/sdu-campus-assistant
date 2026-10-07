import { useEffect, useRef, useState } from 'react';
import { searchRequest, SESSION_EXPIRED } from './auth.js';
import './search.css';
import { FacultyInfo, RoomDescription } from './campus/PlaceDetails.jsx';

export function searchHash(query, page = 1) {
  const params = new URLSearchParams({ q: query.trim(), page: String(page) });
  return `search?${params}`;
}

const kinds = { CLASSROOM: 'Classroom', STAFF_OFFICE: 'Staff office',
  BARREL: 'Lecture hall', UNKNOWN: 'Room type not confirmed' };
const statuses = { PROVISIONAL: 'Provisional entrance recommendation — requires verification',
  UNKNOWN: 'Entrance recommendation confidence is not confirmed' };

function Result({ item }) {
  const room = item.type === 'room';
  const title = room
    ? (item.kind === 'BARREL' ? `${item.name.replace(/^Бочка\s+/i, 'Barrel ')} — ${item.code}` : `Room ${item.code}`)
    : `Block ${item.code}`;
  return <li className="search-result">
    <article aria-label={title}>
      <h2>{title}</h2>
      <p className="search-location">Block {item.block.code}{room && ` · ${item.floor === 0 ? 'Basement' : `Floor ${item.floor}`}`}</p>
      {room && item.name && item.name !== `Room ${item.code}` && item.name !== `Кабинет ${item.code}` && item.kind !== 'BARREL' && <p>{item.name}</p>}
      <FacultyInfo block={item.block} />
      {room && <p>{kinds[item.kind] || kinds.UNKNOWN}</p>}
      <RoomDescription place={item} />
      <p><strong>Recommended entrance: </strong>{({MAIN: 'Main entrance', G: 'Entrance G', I: 'Entrance I'})[item.entrance.code] || 'not recorded'}</p>
      {item.entrance.status !== 'USER_REPORTED' &&
        <p className="search-note">{statuses[item.entrance.status] || statuses.UNKNOWN}</p>}
      <a className="map-result-link" href={`#/map?${new URLSearchParams(item.type === 'room' ? { type: 'room', id: String(item.id) } : { type: 'block', code: item.code })}`}>Show on map</a>
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
      if (!response.ok) throw new Error('Please check your query and try again.');
      if (!Array.isArray(data.results)) throw new Error('Invalid server response.');
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
  return <section className="panel home-panel search-panel" lang="en" aria-labelledby="search-title">
    <p className="eyebrow">Campus search</p>
    <h1 id="search-title" ref={heading} tabIndex="-1">Room and building search</h1>
    <form className="home-search" role="search" onSubmit={submit}>
      <label className="sr-only" htmlFor="room-query">Room number, block or room name</label>
      <input id="room-query" type="search" maxLength={80} value={draft}
        onChange={event => setDraft(event.target.value)} placeholder="E204, Barrel A1, Block E" autoComplete="off" />
      <button className="submit-button" type="submit">Search</button>
    </form>
    <div aria-live="polite" aria-busy={state.status === 'loading'}>
      {state.status === 'empty' && <p>Enter a room number, block or name: for example, E204 or Barrel A1.</p>}
      {state.status === 'loading' && <p role="status">Searching rooms…</p>}
      {state.status === 'error' && <div role="alert"><p>Search unavailable. {state.message}</p>
        <button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry search</button></div>}
      {state.status === 'ready' && <>
        <p role="status">{state.data.count ? `Results: ${state.data.count}` : 'No results. Check the room number or try a block name.'}</p>
        <ul className="search-results">{state.data.results.map(item => <Result key={`${item.type}-${item.id}`} item={item} />)}</ul>
        {(Number(page) > 1 || state.data.next_page) && <nav className="search-pagination" aria-label="Result pages">
          {Number(page) > 1 && <a href={`#${searchHash(query, Number(page) - 1)}`}>← Previous</a>}
          <span>Page {state.data.page}</span>
          {state.data.next_page && <a href={`#${searchHash(query, state.data.next_page)}`}>Next →</a>}
        </nav>}
      </>}
    </div>
    <div className="panel-footer home-footer"><a className="home-profile-link" href="#home">← Back to home</a></div>
  </section>;
}
