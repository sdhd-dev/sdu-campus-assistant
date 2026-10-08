import { useCallback, useEffect, useState } from 'react';
import HomePanel, { SECTIONS, SectionPlaceholder } from './HomePanel.jsx';
import SearchPanel from './SearchPanel.jsx';
import MapPanel from './MapPanel.jsx';
import LoginForm from './LoginForm.jsx';
import ProfilePanel from './ProfilePanel.jsx';
import RegistrationForm from './RegistrationForm.jsx';
import { authRequest, isSession } from './auth.js';

// Pages that only a signed-in person may see. Anyone else is sent to the login page.
const PROTECTED = ['home', 'profile', ...SECTIONS.map((section) => section.hash)];

function nameFromHash(hash) {
  return hash.replace(/^#\/?/, '').split('?')[0];
}

// A signed-in person lands on the home page unless the address names another page.
function routeFromHash(hash) {
  const name = nameFromHash(hash);
  return PROTECTED.includes(name) ? name : 'home';
}

export default function AuthPanel({ onView }) {
  const [state, setState] = useState({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const [hash, setHash] = useState(window.location.hash);
  const [page, setPage] = useState(() => {
    const name = nameFromHash(window.location.hash);
    return name === 'login' || PROTECTED.includes(name) ? 'login' : 'register';
  });
  const [notice, setNotice] = useState('');
  // Stable callback keeps session checking attached for this component's lifetime.
  const signedOut = useCallback((message) => {
    setNotice(message);
    setState({ status: 'anonymous' });
    setPage('login');
    window.location.hash = 'login';
  }, []);

  useEffect(() => {
    function navigate() {
      setHash(window.location.hash);
      if (window.location.hash === '#login') setPage('login');
      if (window.location.hash === '#register') setPage('register');
    }
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    authRequest('me', { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) {
        setState({ status: 'anonymous' });
        // Someone who is not signed in opened a members-only address: show the login page.
        if (PROTECTED.includes(nameFromHash(window.location.hash))) {
          setPage('login');
          window.location.hash = 'login';
        }
      } else {
        if (!response.ok || !isSession(data)) throw new Error('Session unavailable');
        setState({ status: 'authenticated', session: data });
      }
    }).catch(() => { if (!controller.signal.aborted) setState({ status: 'error' }); });
    return () => controller.abort();
  }, [attempt]);

  let view = null;
  let content;
  if (state.status === 'authenticated') {
    view = 'profile';
    const route = routeFromHash(hash);
    if (route === 'profile') {
      content = <ProfilePanel session={state.session} onSignedOut={signedOut} />;
    } else if (route === 'home') {
      content = <HomePanel session={state.session} onSignedOut={signedOut} />;
    } else if (route === 'search') {
      content = <SearchPanel hash={hash} onSignedOut={signedOut} />;
    } else if (route === 'map') {
      content = <MapPanel hash={hash} onSignedOut={signedOut} />;
    } else {
      const section = SECTIONS.find((item) => item.hash === route);
      content = <SectionPlaceholder title={section.title} />;
    }
    content = <><nav className="campus-navigation" aria-label="Main navigation">{[['home', 'Home'], ['search', 'Search'], ['map', 'Campus Map'], ['profile', 'Profile']].map(([key, label]) => <a key={key} href={`#${key}`} aria-current={route === key ? 'page' : undefined}>{label}</a>)}</nav>{content}</>;
  } else if (state.status === 'anonymous') {
    view = page;
    content = page === 'login'
      ? <LoginForm notice={notice} onLogin={(session) => {
        setNotice('');
        setState({ status: 'authenticated', session });
        window.location.hash = 'home';
      }} />
      : <RegistrationForm />;
  } else {
    content = (
      <section className="panel panel-waiting" aria-label="Account status">
        {state.status === 'loading' ? (
          <p className="waiting-line" role="status">
            <span className="waiting-dot" aria-hidden="true" />Checking your session…
          </p>
        ) : (
          <>
            <p role="alert">We couldn’t check your session. Check your connection and try again.</p>
            <button className="secondary-button" onClick={() => setAttempt((value) => value + 1)}>
              Try again
            </button>
          </>
        )}
      </section>
    );
  }

  // The camera follows navigation. Session checking and its error state hold
  // whichever viewpoint is already framed rather than adding a camera move.
  useEffect(() => { if (view) onView(view); }, [onView, view]);

  if (import.meta.env.DEV && hash === '#preview-home') {
    return <div id="authentication"><HomePanel session={{ email: 'student@sdu.edu.kz' }} /></div>;
  }

  return <div id="authentication" className={state.status === 'authenticated' && routeFromHash(hash) === 'map' ? 'map-layout' : undefined} tabIndex="-1" key={view || state.status}>{content}</div>;
}
