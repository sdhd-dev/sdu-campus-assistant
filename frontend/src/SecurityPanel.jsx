import { useCallback, useEffect, useRef, useState } from 'react';
import GoogleButton from './GoogleButton.jsx';
import { SESSION_EXPIRED, authRequest, isSecurity } from './auth.js';

// Sign-in methods and optional two-step verification, shown inside the profile.
export default function SecurityPanel({ onSignedOut }) {
  const [security, setSecurity] = useState(null);
  const [status, setStatus] = useState('loading');
  const [mode, setMode] = useState('idle');
  const [setup, setSetup] = useState(null);
  const [codes, setCodes] = useState(null);
  const [code, setCode] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);
  const lifecycle = useRef(null);
  const codeInput = useRef(null);

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
      setSecurity(data);
      setStatus('ready');
    }).catch(() => { if (!controller.signal.aborted) setStatus('error'); });
    return () => controller.abort();
  }, [onSignedOut, attempt]);

  useEffect(() => { if (mode !== 'idle') codeInput.current?.focus(); }, [mode]);

  // Every change goes through here: one request at a time, with session and CSRF recovery.
  const send = useCallback(async (path, { method = 'POST', body } = {}) => {
    if (busy.current || !security) return null;
    busy.current = true;
    setPending(true);
    setError('');
    setConfirmation('');
    const signal = lifecycle.current.signal;
    try {
      const { response, data } = await authRequest(path, {
        method, signal,
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
  }, [onSignedOut, security]);

  function applySecurity(data) {
    if (!isSecurity(data)) {
      setError('That didn’t work. Please try again.');
      return false;
    }
    setSecurity(data);
    return true;
  }

  const linkGoogle = useCallback(async (credential) => {
    const data = await send('security/google', { body: { credential } });
    if (data && applySecurity(data)) setConfirmation('Google is connected. You can now continue with Google.');
  }, [send]);

  async function unlinkGoogle() {
    const data = await send('security/google', { method: 'DELETE' });
    if (data && applySecurity(data)) setConfirmation('Google is disconnected.');
  }

  function leave() {
    setMode('idle');
    setSetup(null);
    setCode('');
    setError('');
  }

  async function startSetup() {
    const data = await send('security/two-factor/setup', { body: {} });
    if (!data) return;
    if (typeof data.secret !== 'string' || typeof data.qr_code !== 'string'
      || !data.qr_code.startsWith('data:image/svg+xml')) {
      setError('That didn’t work. Please try again.');
      return;
    }
    setSetup({ secret: data.secret, qr: data.qr_code });
    setMode('enable');
  }

  async function submitCode(event) {
    event.preventDefault();
    const enabling = mode === 'enable';
    const data = await send(`security/two-factor/${enabling ? 'enable' : 'disable'}`, {
      body: { code: code.trim() },
    });
    setCode('');
    if (!data || !applySecurity(data)) return;
    setMode('idle');
    setSetup(null);
    if (enabling) {
      setCodes(Array.isArray(data.recovery_codes) ? data.recovery_codes : []);
      setConfirmation('Two-step verification is on.');
    } else {
      setConfirmation('Two-step verification is off.');
    }
  }

  if (status === 'error') {
    return (
      <section className="security" aria-labelledby="security-title">
        <h2 id="security-title" className="section-title">Sign-in and security</h2>
        <div className="setup-error" role="alert">
          <p>We couldn’t load your security settings.</p>
          <button type="button" className="secondary-button"
            onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>
      </section>
    );
  }
  if (status !== 'ready') {
    return (
      <section className="security" aria-labelledby="security-title">
        <h2 id="security-title" className="section-title">Sign-in and security</h2>
        <p className="waiting-line" role="status">
          <span className="waiting-dot" aria-hidden="true" />Loading security settings…
        </p>
      </section>
    );
  }

  const recovery = mode === 'disable';
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
          <span className={`security-badge${security.two_factor_enabled ? ' is-on' : ''}`}>
            {security.two_factor_enabled ? 'On' : 'Off'}
          </span>
        </div>
        <p className="security-text">
          {security.two_factor_enabled
            ? `Sign-in asks for a code from your authenticator app. ${security.recovery_codes_remaining} of 10 recovery codes left.`
            : 'Optional. Ask for a code from an authenticator app every time you sign in.'}
        </p>

        {codes && (
          <div className="recovery-codes">
            <p>
              <strong>Save these recovery codes now.</strong> Each one signs you in once if you
              lose your phone. They won’t be shown again.
            </p>
            <ol>{codes.map((value) => <li key={value}><code>{value}</code></li>)}</ol>
            <button type="button" className="ghost-button" onClick={() => setCodes(null)}>
              I’ve saved them
            </button>
          </div>
        )}

        {mode === 'enable' && setup && (
          <div className="two-factor-setup">
            <ol className="setup-steps">
              <li>Scan this QR code with an authenticator app such as Google Authenticator,
                Microsoft Authenticator, or 1Password.</li>
              <li>Enter the 6-digit code the app shows.</li>
            </ol>
            <img className="qr-code" src={setup.qr} width="180" height="180"
              alt="QR code for adding SDU Campus Assistant to an authenticator app" />
            <p className="setup-key">
              Can’t scan? Enter this key: <code>{setup.secret.match(/.{1,4}/g).join(' ')}</code>
            </p>
          </div>
        )}

        {mode !== 'idle' ? (
          <form onSubmit={submitCode} aria-busy={pending}>
            <div className="form-field">
              <label htmlFor="security-code">
                {recovery ? 'Authentication or recovery code' : 'Authentication code'}
              </label>
              <div className="input-wrap">
                <input id="security-code" ref={codeInput} className="code-input" required
                  autoComplete="one-time-code" inputMode={recovery ? 'text' : 'numeric'}
                  maxLength={recovery ? 11 : 6} autoCapitalize="none" spellCheck={false}
                  readOnly={pending} value={code}
                  onChange={(event) => {
                    setCode(recovery ? event.target.value : event.target.value.replace(/\D/g, ''));
                    setError('');
                  }} />
              </div>
            </div>
            <div className="security-actions">
              <button type="submit" className="ghost-button" disabled={pending || !code.trim()}>
                {pending ? 'Checking…' : recovery ? 'Turn off' : 'Turn on'}
              </button>
              <button type="button" className="secondary-button" disabled={pending} onClick={leave}>
                Cancel
              </button>
            </div>
          </form>
        ) : !codes && (
          <button type="button" className="ghost-button" disabled={pending}
            onClick={security.two_factor_enabled ? () => setMode('disable') : startSetup}>
            {security.two_factor_enabled ? 'Turn off…' : 'Turn on'}
          </button>
        )}
      </div>

      <div className="form-message" role="alert">{error}</div>
      <p className="form-note confirmation" role="status">{confirmation || ' '}</p>
    </section>
  );
}
