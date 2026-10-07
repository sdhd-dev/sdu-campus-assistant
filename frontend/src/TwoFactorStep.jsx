import { useEffect, useRef, useState } from 'react';
import { authRequest, isSession } from './auth.js';

const EXPIRED = 'Your sign-in expired. Please sign in again.';
const OTHER = {
  email: 'Email me a code',
  recovery: 'Use a recovery code',
};

// The second sign-in step. The session stays anonymous until the server accepts a code.
// The code comes by email; a recovery code is the fallback.
export default function TwoFactorStep({ challenge, onLogin, onCancel }) {
  const [token, setToken] = useState(challenge.csrf_token);
  const [method, setMethod] = useState(challenge.methods[0]);
  const [sent, setSent] = useState(challenge.email_code_sent);
  const [wait, setWait] = useState(challenge.resend_in);
  const [code, setCode] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState(
    challenge.methods[0] === 'email' && !challenge.email_code_sent && !challenge.resend_in
      ? 'We couldn’t send the email. Resend the code, or use another method.' : '',
  );
  const [notice, setNotice] = useState('');
  const input = useRef(null);
  const messageRef = useRef(null);
  const inFlight = useRef(false);
  const submission = useRef(null);

  useEffect(() => { input.current?.focus(); }, [method]);
  useEffect(() => () => submission.current?.abort(), []);
  useEffect(() => { if (message) messageRef.current?.focus(); }, [message]);
  // Counts down locally; the server enforces the real limit.
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  async function request(path, body) {
    inFlight.current = true;
    setPending(true);
    setMessage('');
    setNotice('');
    const controller = new AbortController();
    submission.current = controller;
    try {
      const { response, data } = await authRequest(path, {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify(body),
      });
      if (response.status === 401 || response.status === 403) {
        onCancel(EXPIRED);
        return null;
      }
      return { response, data };
    } catch {
      if (!controller.signal.aborted) {
        setMessage('We couldn’t reach the server. Check your connection and try again.');
      }
      return null;
    } finally {
      submission.current = null;
      inFlight.current = false;
      setPending(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || !code.trim()) return;
    const result = await request('two-factor/verify', { method, code: code.trim() });
    if (!result) return;
    const { response, data } = result;
    if (response.ok && isSession(data)) {
      onLogin(data);
      return;
    }
    setCode('');
    setMessage(typeof data?.detail === 'string' ? data.detail : 'That code isn’t valid.');
  }

  async function resend() {
    if (inFlight.current) return;
    const result = await request('two-factor/resend', {});
    if (!result) return;
    const { response, data } = result;
    if (typeof data?.csrf_token === 'string') setToken(data.csrf_token);
    if (Number.isInteger(data?.resend_in)) setWait(data.resend_in);
    if (response.ok) {
      setSent(true);
      setCode('');
      setNotice('We sent a new code.');
    } else {
      setMessage(typeof data?.detail === 'string' ? data.detail : 'We couldn’t send the code.');
    }
  }

  function switchTo(next) {
    setMethod(next);
    setCode('');
    setMessage('');
    setNotice('');
  }

  const email = method === 'email';
  const recovery = method === 'recovery';
  const description = email
    ? (sent
      ? <>We sent a 6-digit code to <strong>{challenge.email_hint}</strong>. It expires in 10 minutes.</>
      : <>Send a 6-digit code to <strong>{challenge.email_hint}</strong>.</>)
    : 'Enter one of the recovery codes you saved when you turned on two-step verification.';

  return (
    <section className="panel" id="login" aria-labelledby="two-factor-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Two-step verification</p>
      <h1 id="two-factor-title">Enter your code</h1>
      <p className="card-description">{description}</p>
      <form onSubmit={submit} aria-busy={pending}>
        <div className="form-field">
          <label htmlFor="two-factor-code">
            {email ? 'Email code' : 'Recovery code'}
          </label>
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
      <p className="form-note confirmation" role="status">{notice || ' '}</p>
      <p className="form-note two-factor-links">
        {email && (
          <button type="button" className="secondary-button" disabled={pending || wait > 0}
            onClick={resend}>{wait > 0 ? `Resend code in ${wait}s` : sent ? 'Resend code' : 'Send code'}</button>
        )}
        {challenge.methods.filter((other) => other !== method).map((other) => (
          <button key={other} type="button" className="secondary-button" disabled={pending}
            onClick={() => switchTo(other)}>{OTHER[other]}</button>
        ))}
        <button type="button" className="secondary-button" disabled={pending}
          onClick={() => onCancel('')}>Back to sign in</button>
      </p>
    </section>
  );
}
