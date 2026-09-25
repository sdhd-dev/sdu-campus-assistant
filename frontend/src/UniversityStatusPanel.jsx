import { useCallback, useEffect, useRef, useState } from 'react';
import { SESSION_EXPIRED, apiRequest, isVerification } from './auth.js';

const LABELS = { STUDENT: 'Student', STAFF: 'Staff' };

function domainList(domains) {
  return domains.map((domain) => `@${domain}`).join(', ');
}

// Confirms Student or Staff status with a code sent to a university address.
// Separate from the self-selected affiliation above it; neither grants permissions.
export default function UniversityStatusPanel({ onSignedOut }) {
  const [state, setState] = useState(null);
  const [status, setStatus] = useState('loading');
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [wait, setWait] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);
  const lifecycle = useRef(null);
  const field = useRef(null);

  const apply = useCallback((data) => {
    setState(data);
    setWait(data.resend_in);
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
      // The server has no university domains configured.
      if (response.status === 404) {
        setStatus('hidden');
        return;
      }
      if (!response.ok || !isVerification(data)) throw new Error('Unavailable');
      apply(data);
      setStatus('ready');
    }).catch(() => { if (!controller.signal.aborted) setStatus('error'); });
    return () => controller.abort();
  }, [apply, onSignedOut, attempt]);

  // Counts down locally; the server enforces the real limit.
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  const stage = state?.pending_email ? 'code' : editing || !state?.verified_affiliation ? 'email' : 'verified';
  useEffect(() => { if (stage !== 'verified' && status === 'ready') field.current?.focus(); }, [stage, status]);

  // Every change goes through here: one request at a time, with session and CSRF recovery.
  async function send(path, { method = 'POST', body } = {}) {
    if (busy.current || !state) return null;
    busy.current = true;
    setPending(true);
    setError('');
    setConfirmation('');
    const signal = lifecycle.current.signal;
    try {
      const { response, data } = await apiRequest(path, {
        method, signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': state.csrf_token },
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
    const data = await send('profile/verification/start', { body: { email: address } });
    if (!data) return;
    setCode('');
    setConfirmation(data.detail);
  }

  async function confirm(event) {
    event.preventDefault();
    const data = await send('profile/verification/confirm', { body: { code } });
    setCode('');
    if (!data) return;
    setEditing(false);
    setEmail('');
    setConfirmation(`Confirmed. Your verified status is ${LABELS[data.verified_affiliation]}.`);
  }

  async function cancel() {
    const data = await send('profile/verification/cancel', { body: {} });
    if (data) setEditing(false);
  }

  async function remove() {
    const data = await send('profile/verification', { method: 'DELETE' });
    if (data) setConfirmation('Your verified status was removed.');
  }

  if (status === 'hidden') return null;
  if (status !== 'ready') {
    return (
      <section className="security" aria-labelledby="university-title">
        <h2 id="university-title" className="section-title">University status</h2>
        {status === 'error' ? (
          <div className="setup-error" role="alert">
            <p>We couldn’t load your university status.</p>
            <button type="button" className="secondary-button"
              onClick={() => setAttempt((value) => value + 1)}>Try again</button>
          </div>
        ) : (
          <p className="waiting-line" role="status">
            <span className="waiting-dot" aria-hidden="true" />Loading university status…
          </p>
        )}
      </section>
    );
  }

  const verified = state.verified_affiliation;
  const domains = [
    state.student_domains.length > 0 && `students ${domainList(state.student_domains)}`,
    state.staff_domains.length > 0 && `staff ${domainList(state.staff_domains)}`,
  ].filter(Boolean).join('; ');

  return (
    <section className="security" aria-labelledby="university-title" aria-busy={pending}>
      <h2 id="university-title" className="section-title">University status</h2>
      <div className="security-item">
        <div className="security-head">
          <p className="security-name">SDU email</p>
          <span className={`security-badge${verified ? ' is-on' : ''}`}>
            {verified ? `Verified ${LABELS[verified]}` : 'Not verified'}
          </span>
        </div>
        <p className="security-text">
          {verified
            ? <>Confirmed with <strong>{state.university_email}</strong>. This is separate from the
              affiliation you chose above.</>
            : 'Optional. Confirm that you study or work at SDU with a code sent to your university email.'}
        </p>

        {stage === 'verified' && (
          <div className="security-actions">
            <button type="button" className="ghost-button" disabled={pending}
              onClick={() => setEditing(true)}>Use another address</button>
            <button type="button" className="secondary-button" disabled={pending}
              onClick={remove}>Remove</button>
          </div>
        )}

        {stage === 'email' && (
          <form onSubmit={requestCode} aria-busy={pending}>
            <div className="form-field">
              <label htmlFor="university-email">University email</label>
              <div className="input-wrap">
                <input id="university-email" ref={field} type="email" required maxLength={254}
                  autoComplete="email" autoCapitalize="none" spellCheck={false}
                  aria-describedby="university-domains" readOnly={pending} value={email}
                  onChange={(event) => { setEmail(event.target.value); setError(''); }} />
              </div>
            </div>
            <p id="university-domains" className="security-text">Accepted addresses: {domains}.</p>
            <div className="security-actions">
              <button type="submit" className="ghost-button" disabled={pending || !email.trim() || wait > 0}>
                {pending ? 'Sending…' : wait > 0 ? `Send code in ${wait}s` : 'Send code'}
              </button>
              {verified && (
                <button type="button" className="secondary-button" disabled={pending}
                  onClick={() => { setEditing(false); setError(''); }}>Cancel</button>
              )}
            </div>
          </form>
        )}

        {stage === 'code' && (
          <form onSubmit={confirm} aria-busy={pending}>
            <p className="security-text">
              Enter the 6-digit code sent to <strong>{state.pending_email}</strong>. It expires in
              10 minutes.
            </p>
            <div className="form-field">
              <label htmlFor="university-code">Verification code</label>
              <div className="input-wrap">
                <input id="university-code" ref={field} className="code-input" required
                  autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}"
                  readOnly={pending} value={code}
                  onChange={(event) => { setCode(event.target.value.replace(/\D/g, '')); setError(''); }} />
              </div>
            </div>
            <div className="security-actions">
              <button type="submit" className="ghost-button" disabled={pending || code.length !== 6}>
                {pending ? 'Checking…' : 'Confirm'}
              </button>
              <button type="button" className="secondary-button" disabled={pending || wait > 0}
                onClick={() => requestCode()}>
                {wait > 0 ? `Resend in ${wait}s` : 'Resend code'}
              </button>
              <button type="button" className="secondary-button" disabled={pending}
                onClick={cancel}>Cancel</button>
            </div>
          </form>
        )}
      </div>

      <div className="form-message" role="alert">{error}</div>
      <p className="form-note confirmation" role="status">{confirmation || ' '}</p>
    </section>
  );
}
