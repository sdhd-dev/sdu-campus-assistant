import { useCallback, useEffect, useState } from 'react';
import LoginForm from './LoginForm.jsx';
import ProfilePanel from './ProfilePanel.jsx';
import RegistrationForm from './RegistrationForm.jsx';
import { authRequest, isSession } from './auth.js';

export default function AuthPanel({ onView }) {
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

  let view = null;
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

  return <div id="authentication" tabIndex="-1" key={view || state.status}>{content}</div>;
}
