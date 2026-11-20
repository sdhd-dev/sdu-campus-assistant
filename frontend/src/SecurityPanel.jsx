import { useCallback, useEffect, useRef, useState } from 'react';
import GoogleButton from './GoogleButton.jsx';
import { SESSION_EXPIRED, authRequest, isSecurity } from './auth.js';

const METHOD_LABELS = { email: 'Email code', recovery: 'Recovery code' };

// Sign-in methods and two-step verification, shown inside the profile. The second step is a
// code sent to the account email; recovery codes come with it for when email can't be reached.
export default function SecurityPanel({ onSignedOut }) {
  const [security, setSecurity] = useState(null);
  const [status, setStatus] = useState('loading');
  // idle | email-on | email-off
  const [mode, setMode] = useState('idle');
  const [codes, setCodes] = useState(null);
  const [code, setCode] = useState('');
  const [method, setMethod] = useState('email');
  const [wait, setWait] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);
  const lifecycle = useRef(null);
  const codeInput = useRef(null);

  const apply = useCallback((data) => {
    setSecurity(data);
    setWait(data.email_resend_in);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    setStatus('loading');
    authRequest('security', { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) {
        onSignedOut(SESSION_EXPIRED);
        return;
      }
      if (!response.ok || !isSecurity(data)) throw new Error('Unavailable');
      apply(data);
      setStatus('ready');
    }).catch(() => { if (!controller.signal.aborted) setStatus('error'); });
    return () => controller.abort();
  }, [apply, onSignedOut, attempt]);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  useEffect(() => { if (mode !== 'idle') codeInput.current?.focus(); }, [mode, method]);

  // Every change goes through here: one request at a time, with session and CSRF recovery.
  const send = useCallback(async (path, { method: verb = 'POST', body } = {}) => {
    if (busy.current || !security) return null;
    busy.current = true;
    setPending(true);
    setError('');
    setConfirmation('');
    const signal = lifecycle.current.signal;
    try {
      const { response, data } = await authRequest(path, {
        method: verb, signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': security.csrf_token },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (response.status === 401) {
        onSignedOut(SESSION_EXPIRED);
        return null;
      }
      if (response.status === 403) {
        setAttempt((value) => value + 1);
        setError('Your security check changed. Please try again.');
        return null;
      }
      if (isSecurity(data)) apply(data);
      if (!response.ok) {
        setError(typeof data?.detail === 'string' ? data.detail : 'That didn’t work. Please try again.');
        return null;
      }
      return data;
    } catch {
      if (!signal.aborted) setError('We couldn’t save that change. Check your connection and try again.');
      return null;
    } finally {
      busy.current = false;
      setPending(false);
    }
  }, [apply, onSignedOut, security]);

  function accept(data) {
    if (!isSecurity(data)) {
      setError('That didn’t work. Please try again.');
      return false;
    }
    apply(data);
    return true;
  }

  const linkGoogle = useCallback(async (credential) => {
    const data = await send('security/google', { body: { credential } });
    if (data && accept(data)) setConfirmation('Google is connected. You can now continue with Google.');
  }, [send]);

  async function unlinkGoogle() {
    const data = await send('security/google', { method: 'DELETE' });
    if (data && accept(data)) setConfirmation('Google is disconnected.');
  }

  function leave() {
    setMode('idle');
    setCode('');
    setError('');
  }

  // Methods that can confirm turning two-step verification off, main one first.
  function confirmMethods() {
    return ['email', security.recovery_codes_remaining > 0 && 'recovery'].filter(Boolean);
  }

  async function emailCode() {
    const data = await send('security/two-factor/email/code', { body: {} });
    if (data) setConfirmation(data.detail);
  }

  async function startEmail() {
    setMode('email-on');
    setCode('');
    if (!security.email_code_pending) await emailCode();
  }

  function startOff() {
    setMode('email-off');
    setMethod('email');
    setCode('');
  }

  const PATHS = {
    'email-on': 'security/two-factor/email/enable',
    'email-off': 'security/two-factor/email/disable',
  };
  const DONE = {
    'email-on': 'Two-step verification is on. We’ll email you a code when you sign in.',
    'email-off': 'Two-step verification is off.',
  };

  async function submitCode(event) {
    event.preventDefault();
    const turningOff = mode.endsWith('-off');
    const body = turningOff ? { method, code: code.trim() } : { code: code.trim() };
    const current = mode;
    const data = await send(PATHS[current], { body });
    setCode('');
    if (!data || !accept(data)) return;
    setMode('idle');
    if (Array.isArray(data.recovery_codes)) setCodes(data.recovery_codes);
    setConfirmation(DONE[current]);
  }

  if (status !== 'ready') {
    return (
      <section className="security" aria-labelledby="security-title">
        <h2 id="security-title" className="section-title">Sign-in and security</h2>
        {status === 'error' ? (
          <div className="setup-error" role="alert">
            <p>We couldn’t load your security settings.</p>
            <button type="button" className="secondary-button"
              onClick={() => setAttempt((value) => value + 1)}>Try again</button>
          </div>
        ) : (
          <p className="waiting-line" role="status">
            <span className="waiting-dot" aria-hidden="true" />Loading security settings…
          </p>
        )}
      </section>
    );
  }

  const turningOff = mode.endsWith('-off');
  const codeKind = turningOff ? method : 'email';
  const codeForm = mode !== 'idle' && (
    <form onSubmit={submitCode} aria-busy={pending}>
      {turningOff && confirmMethods().length > 1 && (
        <fieldset className="method-choice">
          <legend>Confirm with</legend>
          {confirmMethods().map((option) => (
            <label key={option}>
              <input type="radio" name="confirm-method" value={option} checked={method === option}
                onChange={() => { setMethod(option); setCode(''); setError(''); }} />
              {METHOD_LABELS[option]}
            </label>
          ))}
        </fieldset>
      )}
      {codeKind === 'email' && (
        <p className="security-text">
          {security.email_code_pending
            ? <>Enter the 6-digit code sent to <strong>{security.email}</strong>.</>
            : <>We’ll send a 6-digit code to <strong>{security.email}</strong>.</>}{' '}
          <button type="button" className="secondary-button" disabled={pending || wait > 0}
            onClick={emailCode}>
            {security.email_code_pending
              ? (wait > 0 ? `Resend in ${wait}s` : 'Resend code')
              : (wait > 0 ? `Send code in ${wait}s` : 'Send code')}
          </button>
        </p>
      )}
      <div className="form-field">
        <label htmlFor="security-code">
          {turningOff ? 'Verification code' : METHOD_LABELS[codeKind]}
        </label>
        <div className="input-wrap">
          <input id="security-code" ref={codeInput} className="code-input" required
            autoComplete="one-time-code" inputMode={codeKind === 'recovery' ? 'text' : 'numeric'}
            maxLength={codeKind === 'recovery' ? 11 : 6} autoCapitalize="none" spellCheck={false}
            readOnly={pending} value={code}
            onChange={(event) => {
              setCode(codeKind === 'recovery' ? event.target.value : event.target.value.replace(/\D/g, ''));
              setError('');
            }} />
        </div>
      </div>
      <div className="security-actions">
        <button type="submit" className="ghost-button" disabled={pending || !code.trim()}>
          {pending ? 'Checking…' : turningOff ? 'Turn off' : 'Turn on'}
        </button>
        <button type="button" className="secondary-button" disabled={pending} onClick={leave}>
          Cancel
        </button>
      </div>
    </form>
  );

  return (
    <section className="security" aria-labelledby="security-title" aria-busy={pending}>
      <h2 id="security-title" className="section-title">Sign-in and security</h2>

      {(security.google_available || security.google_linked) && (
        <div className="security-item">
          <div className="security-head">
            <p className="security-name">Google</p>
            <span className={`security-badge${security.google_linked ? ' is-on' : ''}`}>
              {security.google_linked ? 'Connected' : 'Not connected'}
            </span>
          </div>
          <p className="security-text">
            {security.google_linked
              ? (security.has_password
                ? 'You can sign in with Google or with your email and password.'
                : 'This account signs in with Google only.')
              : 'Connect your Google account to continue with Google next time.'}
          </p>
          {security.google_linked
            ? security.has_password && (
              <button type="button" className="ghost-button" disabled={pending}
                onClick={unlinkGoogle}>Disconnect Google</button>
            )
            : <GoogleButton onCredential={linkGoogle} />}
        </div>
      )}

      <div className="security-item">
        <div className="security-head">
          <p className="security-name">Two-step verification</p>
          <span className={`security-badge${security.email_two_factor_enabled ? ' is-on' : ''}`}>
            {security.email_two_factor_enabled ? 'On' : 'Off'}
          </span>
        </div>
        <p className="security-text">
          {security.email_two_factor_enabled
            ? <>Each sign-in asks for a code sent to <strong>{security.email}</strong>.</>
            : 'Optional. Get a 6-digit code by email every time you sign in, with Google too.'}
        </p>
        {codeForm}
        {mode === 'idle' && !codes && (
          <button type="button" className="ghost-button" disabled={pending}
            onClick={security.email_two_factor_enabled ? startOff : startEmail}>
            {security.email_two_factor_enabled ? 'Turn off…' : 'Turn on'}
          </button>
        )}
      </div>

      {codes && (
        <div className="recovery-codes">
          <p>
            <strong>Save these recovery codes now.</strong> Each one signs you in once if you
            can’t get an email code. They won’t be shown again.
          </p>
          <ol>{codes.map((value) => <li key={value}><code>{value}</code></li>)}</ol>
          <button type="button" className="ghost-button" onClick={() => setCodes(null)}>
            I’ve saved them
          </button>
        </div>
      )}
      {security.two_factor_enabled && !codes && (
        <p className="security-text recovery-left">
          {security.recovery_codes_remaining} of 10 recovery codes left.
        </p>
      )}

      <div className="form-message" role="alert">{error}</div>
      <p className="form-note confirmation" role="status">{confirmation || ' '}</p>
    </section>
  );
}
