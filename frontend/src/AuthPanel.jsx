import { useCallback, useEffect, useRef, useState } from 'react';
import LoginForm from './LoginForm.jsx';
import RegistrationForm from './RegistrationForm.jsx';
import { authRequest, isSession } from './auth.js';

function SignedIn({ session, onSignedOut }) {
  const [token, setToken] = useState(session.csrf_token);
  const [email, setEmail] = useState(session.email);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const busy = useRef(false);
  const controller = useRef(null);
  const heading = useRef(null);

  useEffect(() => {
    heading.current?.focus();
    const lifecycle = new AbortController();
    controller.current = lifecycle;
    let checking = false;
    async function checkSession() {
      if (busy.current || checking || document.visibilityState === 'hidden') return;
      checking = true;
      try {
        const { response, data } = await authRequest('me', { signal: lifecycle.signal });
        if (lifecycle.signal.aborted || busy.current) return;
        if (response.status === 401) {
          onSignedOut('Your session has expired. Please sign in again.');
        } else {
          if (!response.ok || !isSession(data)) throw new Error('Session unavailable');
          setToken(data.csrf_token);
          setEmail(data.email);
          setMessage('');
        }
      } catch {
        if (!lifecycle.signal.aborted && !busy.current) setMessage('We couldn’t check your session. Check your connection and try again.');
      } finally { checking = false; }
    }
    const timer = setInterval(checkSession, 60000);
    window.addEventListener('focus', checkSession);
    document.addEventListener('visibilitychange', checkSession);
    return () => {
      lifecycle.abort();
      clearInterval(timer);
      window.removeEventListener('focus', checkSession);
      document.removeEventListener('visibilitychange', checkSession);
    };
  }, [onSignedOut]);

  async function logout() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setMessage('');
    try {
      const { response } = await authRequest('logout', {
        method: 'POST', signal: controller.current.signal, headers: { 'X-CSRFToken': token },
      });
      if (response.status === 403) {
        // Another tab may have rotated the CSRF cookie. Refresh before retrying.
        const { response: current, data } = await authRequest('me', { signal: controller.current.signal });
        if (current.status === 401) {
          onSignedOut('Your session has expired. Please sign in again.');
          return;
        }
        if (!current.ok || !isSession(data)) throw new Error('Session unavailable');
        setToken(data.csrf_token);
        setEmail(data.email);
        setMessage('Your security check changed. Please try signing out again.');
        return;
      }
      if (response.status !== 204) throw new Error('Sign-out failed');
      onSignedOut('You have signed out.');
    } catch {
      if (!controller.current.signal.aborted) setMessage('We couldn’t confirm sign-out. Check your connection and try again.');
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  return (
    <section className="registration-card" id="account" aria-labelledby="account-title">
      <p className="eyebrow">YOUR ACCOUNT</p>
      <h2 id="account-title" tabIndex="-1" ref={heading}>You’re signed in</h2>
      <p className="account-email">{email}</p>
      <p className="form-message" role="alert">{message}</p>
      {message && <button className="secondary-button" disabled={pending}
        onClick={() => window.location.reload()}>Check session again</button>}
      <button className="submit-button" onClick={logout} disabled={pending}>
        {pending ? 'Signing out…' : 'Sign out'}
      </button>
    </section>
  );
}

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

  let content;
  if (state.status === 'authenticated') content = <SignedIn session={state.session} onSignedOut={signedOut} />;
  else if (state.status === 'anonymous') content = page === 'login'
    ? <LoginForm notice={notice} onLogin={(session) => { setNotice(''); setState({ status: 'authenticated', session }); }} />
    : <RegistrationForm />;
  else content = (
    <section className="registration-card" aria-label="Account status">
      {state.status === 'loading' ? <p role="status">Checking your session…</p> : <>
        <p role="alert">We couldn’t check your session. Check your connection and try again.</p>
        <button className="secondary-button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
      </>}
    </section>
  );
  return <div id="authentication">{content}</div>;
}
