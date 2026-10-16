import FacilityCard from './campus/FacilityCard.jsx';
import PersonCard, { RoomPeople } from './campus/PersonCard.jsx';
import { useEffect, useRef, useState } from 'react';
import { searchRequest, SESSION_EXPIRED } from './auth.js';
import './search.css';
import { FacultyInfo, RoomDescription, EntranceDescription } from './campus/PlaceDetails.jsx';

export function searchHash(query, page = 1, faculty = '', route = 'search') {
  const params = new URLSearchParams({ q: query.trim(), page: String(page) });
  if (faculty) params.set('faculty', faculty);
  return `${route}?${params}`;
}

const kinds = { CLASSROOM: 'Classroom', STAFF_OFFICE: 'Staff office',
  BARREL: 'Lecture hall', UNKNOWN: 'Room type not confirmed' };
const statuses = { PROVISIONAL: 'Provisional entrance recommendation — requires verification',
  UNKNOWN: 'Entrance recommendation confidence is not confirmed' };

function Result({ item }) {
  if (item.type === 'person') return <li className="search-result"><PersonCard person={item} /></li>;
  if (item.type === 'place') return <li className="search-result"><FacilityCard place={item} /></li>;
  const room = item.type === 'room';
  const title = room
    ? (item.kind === 'BARREL' ? `${item.name.replace(/^Бочка\s+/i, 'Barrel ')} — ${item.code}` : `Room ${item.code}`)
    : item.type === 'place' ? item.name : `Block ${item.code}`;
  return <li className="search-result">
    <article aria-label={title}>
      <h2>{title}</h2>
      <p className="search-location">{item.block ? `Block ${item.block.code}` : 'Block not recorded'}{(room || item.type === 'place') && item.floor !== null && ` · ${item.floor === 0 ? 'Basement' : `Floor ${item.floor}`}`}</p>
      {room && item.name && item.name !== `Room ${item.code}` && item.name !== `Кабинет ${item.code}` && item.kind !== 'BARREL' && <p>{item.name}</p>}
      {item.type === 'place' && item.floor === null && <p>Floor not recorded.</p>}
      <FacultyInfo block={item.block} />
      {room && <p>{kinds[item.kind] || kinds.UNKNOWN}</p>}
      <RoomDescription place={item} />
      {room && <RoomPeople people={item.people} />}
      <p><strong>Recommended entrance: </strong>{({MAIN: 'Main entrance', G: 'Entrance G', I: 'Entrance I'})[item.entrance.code] || 'not recorded'}</p>
      <EntranceDescription description={item.entrance.description} />
      {item.type === 'place' && <p>{item.opening_hours ? `Opening hours: ${item.opening_hours}` : 'Opening hours not recorded'}</p>}
      {item.type === 'place' && item.provisional && <p className="search-note">Facility details require verification.</p>}
      {!['USER_REPORTED', 'PROVISIONAL'].includes(item.entrance.status) &&
        <p className="search-note">{statuses[item.entrance.status] || statuses.UNKNOWN}</p>}
      {(item.type !== 'place' || item.map_available) && <a className="map-result-link" href={`#/map?${new URLSearchParams(['room', 'place'].includes(item.type) ? { type: item.type, id: String(item.id) } : { type: 'block', code: item.code })}`}>Show on map</a>}
      {item.type === 'place' && !item.map_available && <p>Map location not recorded.</p>}
    </article>
  </li>;
}

export default function SearchPanel({ hash, onSignedOut }) {
  const route = hash.replace(/^#?\/?/, '').split('?')[0] === 'directory' ? 'directory' : 'search';
  const staffOnly = route === 'directory';
  const params = new URLSearchParams(hash.split('?')[1] || '');
  const query = params.get('q') || '';
  const page = params.get('page') || '1';
  const faculty = params.get('faculty') || '';
  const [draft, setDraft] = useState(query);
  const [draftFaculty, setDraftFaculty] = useState(faculty);
  const [state, setState] = useState({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus(); }, [query, page]);
  useEffect(() => { setDraft(query); }, [query]);
  useEffect(() => { setDraftFaculty(faculty); }, [faculty]);
  useEffect(() => {
    const controller = new AbortController();
    if (!query.trim()) { setState({ status: 'empty' }); return () => controller.abort(); }
    setState({ status: 'loading' });
    searchRequest(query, page, { signal: controller.signal, faculty, type: staffOnly ? 'person' : '' }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) { onSignedOut(SESSION_EXPIRED); return; }
      if (!response.ok) throw new Error('Please check your query and try again.');
      if (!Array.isArray(data.results)) throw new Error('Invalid server response.');
      setState({ status: 'ready', data });
    }).catch((error) => {
      if (!controller.signal.aborted) setState({ status: 'error', message: error.message });
    });
    return () => controller.abort();
  }, [query, page, faculty, staffOnly, attempt, onSignedOut]);
  function submit(event) {
    event.preventDefault();
    const next = `#${searchHash(draft, 1, draftFaculty, route)}`;
    if (window.location.hash === next) setAttempt(value => value + 1);
    else window.location.hash = next;
  }
  return <section className="panel home-panel search-panel" lang="en" aria-labelledby="search-title">
    <p className="eyebrow">{staffOnly ? 'Faculty & staff' : 'Campus search'}</p>
    <h1 id="search-title" ref={heading} tabIndex="-1">{route === 'directory' ? 'Staff directory' : 'Campus search'}</h1>
    <form className="home-search" role="search" onSubmit={submit}>
      <label className="sr-only" htmlFor="room-query">{staffOnly ? 'Staff name' : 'Room, block, place or staff name'}</label>
      <input id="room-query" type="search" maxLength={80} value={draft}
        onChange={event => setDraft(event.target.value)} placeholder={staffOnly ? 'Search by staff name' : 'E204, Barrel A1 or staff name'} autoComplete="off" />
      <button className="submit-button" type="submit">Search</button>
    </form>
    <label className="directory-filter" htmlFor="directory-faculty">Staff faculty filter
      <select id="directory-faculty" value={draftFaculty} onChange={event => setDraftFaculty(event.target.value)}>
        <option value="">{staffOnly ? 'All faculties' : 'All campus results'}</option><option value="SSBL">{staffOnly ? 'SSBL' : 'SSBL · People only'}</option><option value="SITAM">{staffOnly ? 'SITAM' : 'SITAM · People only'}</option>
      </select>
    </label>
    <div aria-live="polite" aria-busy={state.status === 'loading'}>
      {state.status === 'empty' && <p>{staffOnly ? 'Find faculty and staff by full name or part of a name to see their listed offices.' : 'Enter a room, block, place or staff name: for example, E204, Barrel A1 or Aleksei Kavokin.'}</p>}
      {state.status === 'loading' && <p role="status">{staffOnly ? 'Searching staff…' : 'Searching campus…'}</p>}
      {state.status === 'error' && <div role="alert"><p>Search unavailable. {state.message}</p>
        <button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry search</button></div>}
      {state.status === 'ready' && <>
        <p role="status">{state.data.count ? `Results: ${state.data.count}` : staffOnly ? 'No staff found. Check the spelling, try part of a name or select another faculty.' : 'No results. Check the spelling or try a shorter name or room code.'}</p>
        <ul className="search-results">{state.data.results.map(item => <Result key={`${item.type}-${item.id}`} item={item} />)}</ul>
        {(Number(page) > 1 || state.data.next_page) && <nav className="search-pagination" aria-label="Result pages">
          {Number(page) > 1 && <a href={`#${searchHash(query, Number(page) - 1, faculty, route)}`}>← Previous</a>}
          <span>Page {state.data.page}</span>
          {state.data.next_page && <a href={`#${searchHash(query, state.data.next_page, faculty, route)}`}>Next →</a>}
        </nav>}
      </>}
    </div>
    <div className="panel-footer home-footer"><a className="home-profile-link" href="#home">← Back to home</a></div>
  </section>;
}
