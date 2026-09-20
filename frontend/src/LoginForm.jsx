import { useEffect, useRef, useState } from 'react';
import EyeIcon from './EyeIcon.jsx';
import { authRequest, isSession } from './auth.js';

export default function LoginForm({ onLogin, notice }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [token, setToken] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [setupError, setSetupError] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const messageRef = useRef(null);
  const inFlight = useRef(false);
  const submission = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    setSetupError(false);
    authRequest('login', { signal: controller.signal }).then(({ response, data }) => {
      if (!response.ok || typeof data.csrf_token !== 'string') throw new Error('Unavailable');
      if (!controller.signal.aborted) setToken(data.csrf_token);
    }).catch(() => { if (!controller.signal.aborted) setSetupError(true); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => () => submission.current?.abort(), []);
  useEffect(() => { if (message) messageRef.current?.focus(); }, [message]);

  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || !token) return;
    inFlight.current = true;
    setPending(true);
    setMessage('');
    const controller = new AbortController();
    submission.current = controller;
    try {
      const { response, data } = await authRequest('login', {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (response.status === 400 || response.status === 401) {
        setMessage('Invalid email or password. Please try again.');
      } else if (response.status === 403) {
        setToken('');
        setAttempt((value) => value + 1);
        setMessage('Your security check expired. Please try again once the form is ready.');
      } else {
        if (!response.ok || !isSession(data)) throw new Error('Sign-in failed');
        setPassword('');
        onLogin(data);
      }
    } catch {
      if (!controller.signal.aborted) {
        setMessage('We couldn’t confirm sign-in. Check your connection and try again, or refresh to check your session.');
      }
    } finally {
      submission.current = null;
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section className="panel" id="login" aria-labelledby="login-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Welcome back</p>
      <h1 id="login-title">Sign in</h1>
      <p className="card-description">Sign in to your campus account.</p>
      {notice && <p className="notice" role="status">{notice}</p>}
      <form onSubmit={submit} aria-busy={pending}>
        <p className="required-note">All fields are required.</p>
        <div className="form-field" style={{ '--stagger': '0ms' }}>
          <label htmlFor="login-email">Email</label>
          <div className="input-wrap">
            <input id="login-email" name="email" type="email" autoComplete="username" required
              maxLength={254} autoCapitalize="none" spellCheck={false} value={email} readOnly={pending}
              onChange={(event) => { setEmail(event.target.value); setMessage(''); }} />
          </div>
        </div>
        <div className="form-field login-password" style={{ '--stagger': '55ms' }}>
          <label htmlFor="login-password">Password</label>
          <div className="input-wrap">
            <input id="login-password" name="password" type={visible ? 'text' : 'password'}
              autoComplete="current-password" required maxLength={128} value={password} readOnly={pending}
              onChange={(event) => { setPassword(event.target.value); setMessage(''); }} />
            <button className="visibility-toggle" type="button" aria-label={visible ? 'Hide password' : 'Show password'}
              aria-controls="login-password" aria-pressed={visible} onClick={() => setVisible(!visible)}>
              <EyeIcon visible={visible} />
            </button>
          </div>
        </div>
        {setupError && <div className="setup-error" role="alert">
          <p>Sign-in is unavailable. Check your connection and try again.</p>
          <button type="button" className="secondary-button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>}
        <div className="form-message" role="alert" tabIndex="-1" ref={messageRef}>{message}</div>
        <button className="submit-button" disabled={pending || !token} type="submit">
          <span className={`button-indicator${pending || !token ? ' loading-indicator' : ''}`} aria-hidden="true">
            {pending || !token ? '' : '↗'}
          </span>
          {pending ? 'Signing in…' : token ? 'Sign in' : 'Preparing sign-in…'}
        </button>
      </form>
      <p className="form-note">New to Campus Assistant? <a href="#register">Create an account</a></p>
    </section>
  );
}
