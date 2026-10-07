import { useEffect, useRef } from 'react';
import './home.css';
import { searchHash } from './SearchPanel.jsx';

// Search is available; other sections remain placeholders.
export const SECTIONS = [
  {
    hash: 'search',
    title: 'Search',
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
    title: 'Campus map',
    text: 'Browse the labelled buildings and floors.',
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

export default function HomePanel({ session }) {
  const heading = useRef(null);
  // Move keyboard focus to the heading when the page opens, like the profile page does.
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  return (
    <section className="panel home-panel" aria-labelledby="home-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Campus home</p>
      <h1 id="home-title" tabIndex="-1" ref={heading}>Welcome back</h1>
      <p className="card-description home-email">{session.email}</p>

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

      <nav aria-label="Campus sections">
        <ul className="home-grid">
          {SECTIONS.map((section) => (
            <li key={section.hash}>
              <a className="home-card" href={`#${section.hash}`}>
                <Icon>{section.icon}</Icon>
                <span className="home-card-title">{section.title}</span>
                <span className="home-card-text">{section.text}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="panel-footer home-footer">
        <a className="home-profile-link" href="#profile">Your profile</a>
      </div>
    </section>
  );
}

// Shown for a section that has not been built yet.
export function SectionPlaceholder({ title }) {
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  return (
    <section className="panel home-panel" aria-labelledby="soon-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Coming soon</p>
      <h1 id="soon-title" tabIndex="-1" ref={heading}>{title}</h1>
      <p className="card-description">This part of the assistant is still being built.</p>
      <div className="panel-footer home-footer">
        <a className="home-profile-link" href="#home">← Back to home</a>
      </div>
    </section>
  );
}
