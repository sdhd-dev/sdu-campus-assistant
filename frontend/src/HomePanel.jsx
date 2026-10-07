import { apiRequest, SESSION_EXPIRED } from './auth.js';
import { useEffect, useRef, useState } from 'react';
import './home.css';
import { searchHash } from './SearchPanel.jsx';

// Search is available; other sections remain placeholders.
export const SECTIONS = [
  {
    hash: 'search',
    title: 'Find a place',
    text: 'Find a room, office, or laboratory.',
    icon: (
      <>
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16 16 4.5 4.5" />
      </>
    ),
  },
  {
    hash: 'map',
    title: 'Explore campus map',
    text: 'Explore campus blocks, entrances and lecture halls.',
    icon: (
      <>
        <path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z" />
        <path d="M9 4v14M15 6v14" />
      </>
    ),
  },
  {
    hash: 'services',
    title: 'Services',
    text: 'Opening hours, ID cards, library, and more.',
    icon: (
      <>
        <rect x="4" y="4" width="6.5" height="6.5" rx="1.5" />
        <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" />
        <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" />
        <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" />
      </>
    ),
  },
  {
    hash: 'directory',
    title: 'Directory',
    text: 'Look up where faculty and staff have their offices.',
    icon: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
        <path d="M16 5.5a3 3 0 0 1 0 5.5M18 14.2c1.8.6 3 2.3 3 4.8" />
      </>
    ),
  },
];

function Icon({ children }) {
  return (
    <svg className="home-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export default function HomePanel({ session, onSignedOut }) {
  const [catalog, setCatalog] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest('campus/catalog', { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) { onSignedOut?.(SESSION_EXPIRED); return; }
      if (response.ok) setCatalog(data.quick_places);
    }).catch(() => {});
    return () => controller.abort();
  }, [onSignedOut]);
  const heading = useRef(null);
  // Move keyboard focus to the heading when the page opens, like the profile page does.
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  return (
    <section className="panel home-panel" aria-labelledby="home-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Campus home</p>
      <h1 id="home-title" tabIndex="-1" ref={heading}>Where do you need to go?</h1>
      <p className="card-description home-email">Find rooms, campus blocks and barrel halls.</p>

      <form
        className="home-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          window.location.hash = searchHash(new FormData(event.currentTarget).get('q') || '');
        }}
      >
        <label className="sr-only" htmlFor="home-search-input">Search the campus</label>
        <input
          id="home-search-input"
          type="search"
          name="q"
          placeholder="E204, Barrel A1, Block E"
          maxLength={80}
          autoComplete="off"
        />
        <button className="submit-button" type="submit">Search</button>
      </form>

      <div className="quick-examples" aria-label="Search examples">{['E204', 'Barrel A1', 'Block F'].map(q => <a key={q} href={`#${searchHash(q)}`}>{q}</a>)}</div>
      <nav aria-label="Campus sections">
        <ul className="home-grid">
          {SECTIONS.filter(section => ['search', 'map'].includes(section.hash)).map((section) => (
            <li key={section.hash}>
              <a className="home-card" href={`#${section.hash}`}>
                <Icon>{section.icon}</Icon>
                <span className="home-card-title">{section.title}</span>
                <span className="home-card-text">{section.hash === 'search' ? 'Search rooms, blocks and barrel halls.' : 'Explore campus blocks, entrances and lecture halls.'}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {catalog?.length > 0 && <section className="explore-campus" aria-labelledby="explore-title"><h2 id="explore-title">Explore campus</h2><ul>{catalog.map(item => <li key={`${item.type}-${item.id}`}><a href={`#${searchHash(item.type === 'room' ? item.name : `Block ${item.code}`)}`}>{item.type === 'room' ? item.name : `Block ${item.code}`}</a>{item.block?.faculty_name && <span>{item.block.faculty_name}</span>}</li>)}</ul></section>}
      <section className="planned-features"><h2>Planned features <small>Coming later</small></h2><a href="#services">Services</a> · <a href="#directory">Directory</a></section>
    </section>
  );
}

// Shown for a section that has not been built yet.
export function SectionPlaceholder({ title }) {
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  return (
    <section className="panel home-panel" aria-labelledby="soon-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Coming later</p>
      <h1 id="soon-title" tabIndex="-1" ref={heading}>{title}</h1>
      <p className="card-description">This feature is planned and is not available yet.</p>
      <div className="panel-footer home-footer">
        <a className="home-profile-link" href="#home">← Back to home</a>
      </div>
    </section>
  );
}
