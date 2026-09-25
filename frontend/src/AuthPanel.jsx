import { useCallback, useEffect, useState } from 'react';
import LoginForm from './LoginForm.jsx';
import ProfilePanel from './ProfilePanel.jsx';
import RegistrationForm from './RegistrationForm.jsx';
import { authRequest, isSession } from './auth.js';

const INTRO = {
  register: {
    eyebrow: 'Your campus, a little closer',
    title: <>Welcome to your<br className="desktop-break" /> campus community.</>,
    lead: 'SDU Campus Assistant is taking shape: one place to find your way around '
      + 'campus, look up university services, and keep track of your schedule.',
    note: 'Create an account to reserve your place. It takes about a minute.',
  },
  login: {
    eyebrow: 'Welcome back',
    title: <>Good to see you<br className="desktop-break" /> on campus again.</>,
    lead: 'Sign in with the email you registered. Your session is restored on this device '
      + 'until you sign out.',
    note: 'Signing in brings back your saved campus profile.',
  },
  profile: {
    eyebrow: 'You’re signed in',
    title: <>Let’s set up<br className="desktop-break" /> your campus profile.</>,
    lead: 'Your affiliation tells the assistant which parts of campus life are most '
      + 'relevant to you, from lecture halls to visitor entrances.',
    note: 'Your choice is saved to your account and restored every time you sign in.',
  },
};

export default function AuthPanel() {
  const [state, setState] = useState({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState(window.location.hash === '#login' ? 'login' : 'register');
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
      if (response.status === 401) setState({ status: 'anonymous' });
      else {
        if (!response.ok || !isSession(data)) throw new Error('Session unavailable');
        setState({ status: 'authenticated', session: data });
      }
    }).catch(() => { if (!controller.signal.aborted) setState({ status: 'error' }); });
    return () => controller.abort();
  }, [attempt]);

  let view = 'register';
  let content;
  if (state.status === 'authenticated') {
    view = 'profile';
    content = <ProfilePanel session={state.session} onSignedOut={signedOut} />;
  } else if (state.status === 'anonymous') {
    view = page;
    content = page === 'login'
      ? <LoginForm notice={notice} onLogin={(session) => {
        setNotice('');
        setState({ status: 'authenticated', session });
      }} />
      : <RegistrationForm />;
  } else {
    view = state.status;
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

  const intro = INTRO[view] || INTRO.register;
  return (
    <div className="auth-layout">
      <section className="introduction" key={intro.eyebrow} aria-labelledby="project-title">
        <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />{intro.eyebrow}</p>
        <h1 id="project-title">{intro.title}</h1>
        <p className="intro">{intro.lead}</p>
        <p className="intro-note">{intro.note}</p>
        <div className="project-note">
          <span className="note-line" aria-hidden="true" />
          <p>Built for everyday campus life.<br /><span>Made by a university team.</span></p>
        </div>
      </section>
      <div id="authentication" tabIndex="-1" key={view}>{content}</div>
    </div>
  );
}
