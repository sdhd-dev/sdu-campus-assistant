import { useEffect, useRef, useState } from 'react';
import { SESSION_EXPIRED, apiRequest, isVerification } from './auth.js';

const LABELS = { STUDENT: 'Student', STAFF: 'Staff' };

// "Verify your role": SDU email → code → the server sets the role. Closing it leaves
// the current role as it was. The server checks the domain against the role again.
export default function VerifyRoleDialog({ role, onClose, onVerified, onSignedOut }) {
  const [state, setState] = useState(null);
  const [status, setStatus] = useState('loading');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [wait, setWait] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [attempt, setAttempt] = useState(0);
  const dialog = useRef(null);
  const field = useRef(null);
  const busy = useRef(false);
  const lifecycle = useRef(null);
  const latest = useRef(null);
  const label = LABELS[role];

  function apply(data) {
    setState(data);
    latest.current = data;
    setWait(data.resend_in);
  }

  useEffect(() => {
    // StrictMode mounts effects twice in development; showModal throws on an open dialog.
    if (!dialog.current.open) dialog.current.showModal();
    // Leaving without verifying drops any code sent from this dialog.
    return () => {
      const data = latest.current;
      if (!data?.pending_email) return;
      apiRequest('profile/verification/cancel', {
        method: 'POST', keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': data.csrf_token },
        body: '{}',
      }).catch(() => {});
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    setStatus('loading');
    apiRequest('profile/verification', { signal: controller.signal }).then(({ response, data }) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) {
        onSignedOut(SESSION_EXPIRED);
        return;
      }
      if (!response.ok || !isVerification(data)) throw new Error('Unavailable');
      apply(data);
      setStatus('ready');
    }).catch(() => { if (!controller.signal.aborted) setStatus('error'); });
    return () => controller.abort();
  }, [onSignedOut, attempt]);

  // Counts down locally; the server enforces the real limit.
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  const stage = state?.pending_email ? 'code' : 'email';
  useEffect(() => { if (status === 'ready') field.current?.focus(); }, [stage, status]);

  async function send(path, body) {
    if (busy.current || !state) return null;
    busy.current = true;
    setPending(true);
    setError('');
    setNotice('');
    const signal = lifecycle.current.signal;
    try {
      const { response, data } = await apiRequest(path, {
        method: 'POST', signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': state.csrf_token },
        body: JSON.stringify(body),
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
      // Refusals still carry the current state, such as a burned code or a new wait.
      if (isVerification(data)) apply(data);
      if (!response.ok) {
        setError(typeof data?.detail === 'string' ? data.detail : 'That didn’t work. Please try again.');
        return null;
      }
      if (!isVerification(data)) throw new Error('Unexpected response');
      return data;
    } catch {
      if (!signal.aborted) setError('We couldn’t reach the server. Check your connection and try again.');
      return null;
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function requestCode(event) {
    event?.preventDefault();
    const address = stage === 'code' ? state.pending_email : email.trim();
    const data = await send('profile/verification/start', { email: address, role });
    if (!data) return;
    setCode('');
    setNotice(data.detail);
  }

  async function verify(event) {
    event.preventDefault();
    const data = await send('profile/verification/confirm', { code });
    setCode('');
    if (!data) return;
    if (data.verified_affiliation !== role || data.profile_type !== role) {
      setError('That didn’t work. Please try again.');
      return;
    }
    latest.current = null;
    onVerified(label);
  }

  async function changeAddress() {
    const data = await send('profile/verification/cancel', {});
    if (data) setEmail('');
  }

  const domains = state ? state[role === 'STUDENT' ? 'student_domains' : 'staff_domains'] : [];

  return (
    // Escape and the close button both end here; the role is only ever set by the server.
    <dialog ref={dialog} className="role-dialog" aria-labelledby="role-dialog-title"
      aria-describedby="role-dialog-description" onClose={onClose}
      onCancel={(event) => { if (pending) event.preventDefault(); }}>
      <div className="role-dialog-head">
        <h2 id="role-dialog-title">Verify your role</h2>
        <button type="button" className="dialog-close" aria-label="Close" disabled={pending}
          onClick={() => dialog.current.close()}>×</button>
      </div>
      <p id="role-dialog-description" className="security-text">
        To choose <strong>{label}</strong>, confirm your SDU email. Your role changes only after
        the code is verified.
      </p>

      {status === 'error' && (
        <div className="setup-error" role="alert">
          <p>We couldn’t load verification.</p>
          <button type="button" className="secondary-button"
            onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>
      )}
      {status === 'loading' && (
        <p className="waiting-line" role="status">
          <span className="waiting-dot" aria-hidden="true" />Loading…
        </p>
      )}

      {status === 'ready' && stage === 'email' && (
        <form onSubmit={requestCode} aria-busy={pending}>
          <div className="form-field">
            <label htmlFor="role-email">SDU email</label>
            <div className="input-wrap">
              <input id="role-email" ref={field} type="email" required maxLength={254}
                autoComplete="email" autoCapitalize="none" spellCheck={false}
                aria-describedby="role-domains" readOnly={pending} value={email}
                onChange={(event) => { setEmail(event.target.value); setError(''); }} />
            </div>
          </div>
          <p id="role-domains" className="security-text">
            {domains.length > 0
              ? `${label} addresses end in ${domains.map((domain) => `@${domain}`).join(' or ')}.`
              : `No ${label.toLowerCase()} domains are configured.`}
          </p>
          <div className="security-actions">
            <button type="submit" className="ghost-button"
              disabled={pending || !email.trim() || wait > 0 || domains.length === 0}>
              {pending ? 'Sending…' : wait > 0 ? `Send code in ${wait}s` : 'Send code'}
            </button>
          </div>
        </form>
      )}

      {status === 'ready' && stage === 'code' && (
        <form onSubmit={verify} aria-busy={pending}>
          <p className="security-text">
            Enter the 6-digit code sent to <strong>{state.pending_email}</strong>. It expires in
            10 minutes.
          </p>
          <div className="form-field">
            <label htmlFor="role-code">Verification code</label>
            <div className="input-wrap">
              <input id="role-code" ref={field} className="code-input" required
                autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}"
                readOnly={pending} value={code}
                onChange={(event) => { setCode(event.target.value.replace(/\D/g, '')); setError(''); }} />
            </div>
          </div>
          <div className="security-actions">
            <button type="submit" className="ghost-button" disabled={pending || code.length !== 6}>
              {pending ? 'Checking…' : 'Verify'}
            </button>
            <button type="button" className="secondary-button" disabled={pending || wait > 0}
              onClick={() => requestCode()}>
              {wait > 0 ? `Resend in ${wait}s` : 'Resend code'}
            </button>
            <button type="button" className="secondary-button" disabled={pending}
              onClick={changeAddress}>Use another address</button>
          </div>
        </form>
      )}

      <div className="form-message" role="alert">{error}</div>
      <p className="form-note confirmation" role="status">{notice || ' '}</p>
    </dialog>
  );
}
