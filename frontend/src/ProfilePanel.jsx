import { useCallback, useEffect, useRef, useState } from 'react';
import SecurityPanel from './SecurityPanel.jsx';
import { SESSION_EXPIRED as EXPIRED, apiRequest, authRequest, isProfile } from './auth.js';

// The server owns the list of values; this only adds copy and an icon for the ones we know.
const DETAILS = {
  STUDENT: {
    description: 'Enrolled in a degree programme at the university.',
    icon: <path d="M2 8.2 12 3.5l10 4.7-10 4.7L2 8.2Zm4 3.1v4.9c0 1.6 2.7 2.9 6 2.9s6-1.3 6-2.9v-4.9M20 9.4v5.4" />,
  },
  STAFF: {
    description: 'Teaching, research, or administrative employee.',
    icon: <path d="M3.5 20.5V6.8l7-3.3v17M10.5 20.5h10V9.6l-10-2.8M6.6 9.9v.01M6.6 13.6v.01M6.6 17.2v.01M14.2 12.4v5.2M17.4 12.4v5.2" />,
  },
  VISITOR: {
    description: 'Guest, applicant, or partner exploring the campus.',
    icon: <path d="M12 21.5s7-5.8 7-11a7 7 0 1 0-14 0c0 5.2 7 11 7 11Z M12 12.6a2.6 2.6 0 1 0 0-5.2 2.6 2.6 0 0 0 0 5.2Z" />,
  },
};

function OptionIcon({ value }) {
  const icon = DETAILS[value]?.icon;
  if (!icon) return null;
  return (
    <svg className="option-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {icon}
    </svg>
  );
}

export default function ProfilePanel({ session, onSignedOut }) {
  const [token, setToken] = useState(session.csrf_token);
  const [email, setEmail] = useState(session.email);
  const [options, setOptions] = useState(null);
  const [saved, setSaved] = useState('');
  const [selected, setSelected] = useState('');
  const [status, setStatus] = useState('loading');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);
  const lifecycle = useRef(null);
  const heading = useRef(null);

  const applyProfile = useCallback((data) => {
    setToken(data.csrf_token);
    setEmail(data.email);
    setOptions(data.profile_types);
    setSaved(data.profile_type);
    // A save in flight owns the selection; a background refresh must not overwrite it.
    if (!busy.current) setSelected(data.profile_type);
    setStatus('ready');
  }, []);

  useEffect(() => { heading.current?.focus(); }, []);

  // Load the saved profile, then keep the session, token, and profile fresh.
  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    let checking = false;

    async function load(background) {
      if (checking || (background && (busy.current || document.visibilityState === 'hidden'))) return;
      checking = true;
      if (!background) setStatus('loading');
      try {
        const { response, data } = await apiRequest('profile', { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (response.status === 401) {
          onSignedOut(EXPIRED);
          return;
        }
        if (!response.ok || !isProfile(data)) throw new Error('Profile unavailable');
        applyProfile(data);
        if (!busy.current) setError('');
      } catch {
        if (controller.signal.aborted || busy.current) return;
        if (background) setError('We couldn’t refresh your session. Check your connection.');
        else setStatus('error');
      } finally {
        checking = false;
      }
    }

    load(false);
    const refresh = () => load(true);
    const timer = setInterval(refresh, 60000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [applyProfile, onSignedOut, attempt]);

  async function save(event) {
    event.preventDefault();
    if (busy.current || status !== 'ready' || !selected) return;
    busy.current = true;
    setPending(true);
    setError('');
    setConfirmation('');
    const signal = lifecycle.current.signal;
    try {
      const { response, data } = await apiRequest('profile', {
        method: 'PATCH', signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify({ profile_type: selected }),
      });
      if (response.status === 401) {
        onSignedOut(EXPIRED);
        return;
      }
      if (response.status === 403) {
        // Another tab may have rotated the CSRF secret. Refresh the token before retrying.
        const { response: current, data: fresh } = await apiRequest('profile', { signal });
        if (current.status === 401) {
          onSignedOut(EXPIRED);
          return;
        }
        if (!current.ok || !isProfile(fresh)) throw new Error('Profile unavailable');
        // applyProfile keeps the pending selection while a save is in flight.
        applyProfile(fresh);
        setError('Your security check changed. Please try saving again.');
        return;
      }
      if (response.status === 400) {
        setError('That affiliation isn’t available. Please choose one of the options above.');
        return;
      }
      if (response.status === 503) {
        setError('Saving your profile is temporarily unavailable. Please try again.');
        return;
      }
      if (!response.ok || !isProfile(data)) throw new Error('Save failed');
      applyProfile(data);
      const label = data.profile_types.find((option) => option.value === data.profile_type)?.label;
      setConfirmation(`Saved. Your affiliation is ${label}.`);
    } catch {
      if (!signal.aborted) {
        setError('We couldn’t save your profile. Check your connection and try again.');
      }
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function logout() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError('');
    setConfirmation('');
    const signal = lifecycle.current.signal;
    try {
      const { response } = await authRequest('logout', {
        method: 'POST', signal, headers: { 'X-CSRFToken': token },
      });
      if (response.status === 403) {
        const { response: current, data } = await apiRequest('profile', { signal });
        if (current.status === 401) {
          onSignedOut(EXPIRED);
          return;
        }
        if (!current.ok || !isProfile(data)) throw new Error('Profile unavailable');
        applyProfile(data);
        setError('Your security check changed. Please try signing out again.');
        return;
      }
      if (response.status !== 204) throw new Error('Sign-out failed');
      onSignedOut('You have signed out.');
    } catch {
      if (!signal.aborted) {
        setError('We couldn’t confirm sign-out. Check your connection and try again.');
      }
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  const dirty = Boolean(selected) && selected !== saved;

  return (
    <section className="panel profile-panel" id="profile" aria-labelledby="profile-title">
      <p className="eyebrow"><span className="eyebrow-rule" aria-hidden="true" />Your account</p>
      <h1 id="profile-title" tabIndex="-1" ref={heading}>Your campus profile</h1>
      <p className="card-description">Change your affiliation at any time.</p>

      <div className="account-row">
        <span className="account-label">Signed in as</span>
        <p className="account-email">{email}</p>
      </div>

      {status === 'error' ? (
        <div className="setup-error" role="alert">
          <p>We couldn’t load your profile. Check your connection and try again.</p>
          <button type="button" className="secondary-button"
            onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>
      ) : status !== 'ready' ? (
        <p className="waiting-line" role="status">
          <span className="waiting-dot" aria-hidden="true" />Loading your saved profile…
        </p>
      ) : (
        <form onSubmit={save} aria-busy={pending}>
          <fieldset className="profile-options">
            <legend>University affiliation</legend>
            <div className="option-list">
              {options.map((option, index) => (
                <label className="profile-option" key={option.value}
                  style={{ '--stagger': `${index * 60}ms` }}>
                  <input type="radio" name="profile_type" value={option.value}
                    checked={selected === option.value}
                    onChange={() => {
                      setSelected(option.value);
                      setError('');
                      setConfirmation('');
                    }} />
                  <span className="option-mark" aria-hidden="true" />
                  <span className="option-body">
                    <span className="option-title">
                      <OptionIcon value={option.value} />
                      {option.label}
                    </span>
                    <span className="option-text">{DETAILS[option.value]?.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <p className="option-note">
            Affiliation describes your relationship with the university. It does not grant
            administrative access.
          </p>

          <div className="form-message" role="alert">{error}</div>
          <button className={`submit-button${!pending && !dirty ? ' is-saved' : ''}`}
            type="submit" disabled={pending || !dirty}>
            <span className={`button-indicator${pending ? ' loading-indicator' : ''}`} aria-hidden="true">
              {pending ? '' : dirty ? '↗' : '✓'}
            </span>
            {pending ? 'Saving…' : dirty ? 'Save profile' : 'Saved'}
          </button>
          <p className="form-note confirmation" role="status">
            {pending ? 'Saving your profile…' : confirmation || '\u00a0'}
          </p>
        </form>
      )}

      <SecurityPanel onSignedOut={onSignedOut} />

      <div className="panel-footer">
        <button type="button" className="ghost-button" onClick={logout} disabled={pending}>
          Sign out
        </button>
      </div>
    </section>
  );
}
