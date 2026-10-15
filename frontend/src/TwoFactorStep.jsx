import { useEffect, useRef, useState } from 'react';
import { authRequest, isSession } from './auth.js';

const EXPIRED = 'Your sign-in expired. Please sign in again.';

// The second sign-in step. The session stays anonymous until the server accepts a code.
export default function TwoFactorStep({ token, onLogin, onCancel }) {
  const [code, setCode] = useState('');
  const [recovery, setRecovery] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const input = useRef(null);
  const messageRef = useRef(null);
  const inFlight = useRef(false);
  const submission = useRef(null);

  useEffect(() => { input.current?.focus(); }, [recovery]);
  useEffect(() => () => submission.current?.abort(), []);
  useEffect(() => { if (message) messageRef.current?.focus(); }, [message]);

  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || !code.trim()) return;
    inFlight.current = true;
    setPending(true);
    setMessage('');
    const controller = new AbortController();
    submission.current = controller;
    try {
      const { response, data } = await authRequest('two-factor/verify', {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify({ code: code.trim() }),
      });
      if (response.status === 401 || response.status === 403) {
        onCancel(EXPIRED);
      } else if (response.status === 400 || response.status === 429) {
        setCode('');
        setMessage(typeof data?.detail === 'string' ? data.detail : 'That code isn’t valid.');
      } else {
        if (!response.ok || !isSession(data)) throw new Error('Sign-in failed');
        onLogin(data);
      }
    } catch {
      if (!controller.signal.aborted) {
        setMessage('We couldn’t confirm sign-in. Check your connection and try again.');
      }
    } finally {
      submission.current = null;
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section className="panel" id="login" aria-labelledby="two-factor-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Two-step verification</p>
      <h1 id="two-factor-title">Enter your code</h1>
      <p className="card-description">
        {recovery
          ? 'Enter one of the recovery codes you saved when you turned on two-step verification.'
          : 'Open your authenticator app and enter the 6-digit code for SDU Campus Assistant.'}
      </p>
      <form onSubmit={submit} aria-busy={pending}>
        <div className="form-field">
          <label htmlFor="two-factor-code">{recovery ? 'Recovery code' : 'Authentication code'}</label>
          <div className="input-wrap">
            <input id="two-factor-code" name="code" ref={input} required readOnly={pending}
              className="code-input" autoComplete="one-time-code" autoCapitalize="none" spellCheck={false}
              inputMode={recovery ? 'text' : 'numeric'} maxLength={recovery ? 11 : 6}
              pattern={recovery ? undefined : '[0-9]{6}'} value={code}
              onChange={(event) => {
                setCode(recovery ? event.target.value : event.target.value.replace(/\D/g, ''));
                setMessage('');
              }} />
          </div>
        </div>
        <div className="form-message" role="alert" tabIndex="-1" ref={messageRef}>{message}</div>
        <button className="submit-button" disabled={pending || !code.trim()} type="submit">
          <span className={`button-indicator${pending ? ' loading-indicator' : ''}`} aria-hidden="true">
            {pending ? '' : '↗'}
          </span>
          {pending ? 'Checking…' : 'Verify and sign in'}
        </button>
      </form>
      <p className="form-note">
        <button type="button" className="secondary-button" disabled={pending} onClick={() => {
          setRecovery(!recovery);
          setCode('');
          setMessage('');
        }}>
          {recovery ? 'Use your authenticator app' : 'Use a recovery code'}
        </button>
        {' · '}
        <button type="button" className="secondary-button" disabled={pending}
          onClick={() => onCancel('')}>Back to sign in</button>
      </p>
    </section>
  );
}
