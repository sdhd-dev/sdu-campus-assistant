import { useEffect, useRef, useState } from 'react';
import { locationRequest, searchRequest, SESSION_EXPIRED } from './auth.js';
import CampusMap, { MAP_BLOCKS, MAP_ENTRANCES } from './map/CampusMap.jsx';
import './map/map.css';

const entryName = code => ({ MAIN: 'Main entrance', G: 'Entrance G', I: 'Entrance I' })[code] || (code ? `Entrance ${code}` : 'Entrance not recorded');
export function mapHash(type, key) {
  return `/map?${new URLSearchParams(type === 'room' ? { type, id: String(key) } : { type, code: key })}`;
}
const kindName = { CLASSROOM: 'Classroom', STAFF_OFFICE: 'Staff office', BARREL: 'Lecture hall', UNKNOWN: 'Room type not confirmed' };
function placeTitle(place) {
  if (place.type === 'room') return `${place.map.barrel_code ? `Barrel ${place.map.barrel_label} — ` : ''}${place.code}`;
  return place.type === 'entrance' ? entryName(place.code) : `Block ${place.code}`;
}

export default function MapPanel({ hash, onSignedOut }) {
  const parameterString = hash.split('?')[1] || '';
  const [selection, setSelection] = useState({ status: 'empty' });
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ status: 'empty' });
  const [search, setSearch] = useState(null);
  const [searchAttempt, setSearchAttempt] = useState(0);
  const [zoom, setZoom] = useState(1);
  const heading = useRef(null);
  const scroller = useRef(null);
  const searchController = useRef(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => {
    const controller = new AbortController();
    if (!parameterString) { setSelection({ status: 'empty' }); return () => controller.abort(); }
    setSelection({ status: 'loading' });
    locationRequest(new URLSearchParams(parameterString), { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) { onSignedOut(SESSION_EXPIRED); return; }
      if (response.status === 404 || response.status === 400) {
        setSelection({ status: 'unknown', message: data.detail }); return;
      }
      if (!response.ok || !data.map) throw new Error('Location unavailable');
      setSelection({ status: 'ready', place: data });
    }).catch(() => { if (!controller.signal.aborted) setSelection({ status: 'error' }); });
    return () => controller.abort();
  }, [parameterString, attempt, onSignedOut]);
  useEffect(() => {
    const controller = new AbortController();
    searchController.current = controller;
    if (!search?.trim()) { setResults({ status: 'empty' }); return () => controller.abort(); }
    setResults({ status: 'loading' });
    searchRequest(search, 1, { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) { onSignedOut(SESSION_EXPIRED); return; }
      if (!response.ok || !Array.isArray(data.results)) throw new Error('Search unavailable');
      setResults({ status: 'ready', data });
      // Exact, unambiguous searches can select immediately. Partial searches show choices.
      if (data.count === 1) choose(data.results[0].type, data.results[0].type === 'room' ? data.results[0].id : data.results[0].code, true);
    }).catch(() => { if (!controller.signal.aborted) setResults({ status: 'error' }); });
    return () => controller.abort();
  }, [search, searchAttempt, onSignedOut]);
  function choose(type, key, fromSearch = false) {
    if (!fromSearch) { searchController.current?.abort(); setSearch(null); }
    window.location.hash = mapHash(type, key);
  }
  function reset() {
    setZoom(1);
    scroller.current?.scrollTo({ top: 0, left: 0 });
  }
  const place = selection.status === 'ready' ? selection.place : null;
  const mapped = place?.map;
  const missingBlock = mapped?.block_code && !MAP_BLOCKS.includes(mapped.block_code);
  const missingEntry = mapped?.entrance_code && !MAP_ENTRANCES.includes(mapped.entrance_code);
  return <section className="panel map-panel" lang="en" aria-labelledby="map-title">
    <p className="eyebrow">Campus explorer</p>
    <h1 id="map-title" tabIndex="-1" ref={heading}>Campus map</h1>
    <p className="card-description">Select a building or entrance to understand its location.</p>
    <form className="home-search" role="search" onSubmit={event => {
      event.preventDefault(); setSearch(query.trim()); setSearchAttempt(value => value + 1);
    }}>
      <label className="sr-only" htmlFor="map-query">Room number, block or barrel</label>
      <input id="map-query" value={query} onChange={event => setQuery(event.target.value)} maxLength={80}
        type="search" placeholder="E204, Block H or Barrel D2" />
      <button className="submit-button" type="submit">Search</button>
    </form>
    <div className="map-search-feedback" aria-live="polite">
      {results.status === 'empty' && <p>Search rooms from the campus inventory, or select a block below.</p>}
      {results.status === 'loading' && <p role="status">Searching campus inventory…</p>}
      {results.status === 'error' && <div role="alert"><p>Search unavailable. Please try again.</p>
        <button className="secondary-button" onClick={() => setSearchAttempt(value => value + 1)}>Retry search</button></div>}
      {results.status === 'ready' && <>
        {!results.data.count && <p>No match in the campus inventory. Try E204 or Barrel D2.</p>}
        <ul className="map-search-results">{results.data.results.map(item => <li key={`${item.type}-${item.id}`}>
          <a href={`#${mapHash(item.type, item.type === 'room' ? item.id : item.code)}`}>
            {item.type === 'block' ? `Block ${item.code}` : item.code} · Show on map
          </a>
        </li>)}</ul>
        {results.data.next_page && <a href={`#search?${new URLSearchParams({q: search})}`}>View all search results</a>}
      </>}
    </div>
    <div className="map-columns">
      <div className="map-drawing">
        <div className="map-toolbar" role="group" aria-label="Map zoom controls">
          <button className="secondary-button" onClick={() => setZoom(value => Math.min(3, value + .5))} disabled={zoom >= 3} aria-label="Zoom in">+</button>
          <button className="secondary-button" onClick={() => setZoom(value => Math.max(1, value - .5))} disabled={zoom <= 1} aria-label="Zoom out">−</button>
          <button className="secondary-button" onClick={reset}>Reset</button>
          <span role="status" aria-label="Zoom level">{Math.round(zoom * 100)}%</span>
        </div>
        <div className="map-scroll" ref={scroller} tabIndex="0" aria-label="Scrollable campus map">
          <div className="map-canvas" style={{ width: `min(${zoom * 100}%, calc(var(--map-fit-height) * ${zoom * 600 / 1100}))` }}>
            <CampusMap block={mapped?.block_code} entrance={mapped?.entrance_code} barrel={mapped?.barrel_code} onSelect={choose} />
          </div>
        </div>
        <div className="map-legend"><span><i className="selected-swatch" aria-hidden="true" />Selected location</span><span>● Entrance</span></div>
        <div className="map-block-choices" role="group" aria-label="Select a block">
          {MAP_BLOCKS.map(code => <button key={code} className="secondary-button" aria-label={`Select Block ${code}`}
            aria-pressed={mapped?.block_code === code} onClick={() => choose('block', code)}>{code}</button>)}
        </div>
        <div className="map-entry-choices" role="group" aria-label="Select an entrance">
          {MAP_ENTRANCES.map(code => <button key={code} className="secondary-button" aria-pressed={mapped?.entrance_code === code}
            onClick={() => choose('entrance', code)}>{entryName(code)}</button>)}
        </div>
      </div>
      <aside className="map-place" aria-label="Selected location" aria-live="polite">
        {selection.status === 'empty' && <p>Select a block, entrance or search result to see its location.</p>}
        {selection.status === 'loading' && <p role="status">Loading location…</p>}
        {selection.status === 'unknown' && <div role="alert"><h2>Unknown location</h2><p>{selection.message}</p><p>Select a recorded block or search again.</p></div>}
        {selection.status === 'error' && <div role="alert"><p>Location unavailable. Please try again.</p>
          <button className="secondary-button" onClick={() => setAttempt(value => value + 1)}>Retry location</button></div>}
        {place && <>
          <h2>{placeTitle(place)}</h2>
          <p className="map-summary">{place.type === 'room' && `${place.code} · `}
            {mapped.block_code && `Block ${mapped.block_code} · `}
            {place.type === 'room' && `${place.floor === 0 ? 'Basement' : `Floor ${place.floor}`} · `}
            {entryName(mapped.entrance_code)}</p>
          {place.type === 'room' && <p>{kindName[place.kind] || kindName.UNKNOWN}</p>}
          {place.type === 'room' && place.provisional && <p className="map-notice">Provisional room record — existence requires verification.</p>}
          {place.type === 'room' && <p>Shown by building only. Room positions and floor plans are not available.</p>}
          {mapped.context_only && <p>Context building. Facility details and entrance recommendation are not confirmed.</p>}
          {mapped.block_code === 'B' && <p>Library area — boundaries require confirmation.</p>}
          {!mapped.entrance_code && <p>Entrance information is not available for this location.</p>}
          {place.entrance?.status === 'PROVISIONAL' && <p className="map-notice">Provisional entrance recommendation — requires verification.</p>}
          {place.entrance?.status === 'UNKNOWN' && mapped.entrance_code && <p>Entrance recommendation confidence is not confirmed.</p>}
          {mapped.entrance_position_provisional && <p className="map-notice">Entrance I position is provisional.</p>}
          {missingBlock && <p role="alert">This building has no shape on the current map.</p>}
          {missingEntry && <p role="alert">This entrance has no marker on the current map.</p>}
          {place.kind === 'BARREL' && !mapped.barrel_code && <p>Physical barrel location is not confirmed.</p>}
        </>}
      </aside>
    </div>
    <p className="map-disclaimer">Schematic campus map · Not to scale. Library boundaries and Entrance I position require confirmation. Accounting Office and Red Hall locations are pending.</p>
    <div className="panel-footer home-footer"><a className="home-profile-link" href="#home">← Back to home</a></div>
  </section>;
}
