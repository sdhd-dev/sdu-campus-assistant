import { useEffect, useRef, useState } from 'react';

const endpoint = '/api/auth/register/';
const emptyValues = { email: '', password: '', password_confirmation: '' };
const fields = [
  { name: 'email', label: 'Email', autoComplete: 'email' },
  { name: 'password', label: 'Password', autoComplete: 'new-password' },
  { name: 'password_confirmation', label: 'Confirm password', autoComplete: 'new-password' },
];

function validate(name, values) {
  const value = values[name];
  if (!value || (name === 'email' && !value.trim())) return 'This field is required.';
  if (name === 'email') {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())) return 'Enter a valid email address.';
    if (value.trim().length > 254) return 'Use an email address of 254 characters or fewer.';
  } else if (value.length > 128) return 'Use 128 characters or fewer.';
  if (name === 'password_confirmation' && value !== values.password) return 'Passwords do not match.';
  return '';
}

function EyeIcon({ visible }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {visible && <path d="m3 3 18 18" />}
    </svg>
  );
}

export default function RegistrationForm() {
  const [values, setValues] = useState(emptyValues);
  const [errors, setErrors] = useState({});
  const [visible, setVisible] = useState({});
  const [configuration, setConfiguration] = useState(null);
  const [setupError, setSetupError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [createdEmail, setCreatedEmail] = useState('');
  const [focusTarget, setFocusTarget] = useState(null);
  const controls = useRef({});
  const inFlight = useRef(false);
  const submission = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 8000);
    setSetupError(false);
    async function prepare() {
      try {
        const response = await fetch(endpoint, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error('Registration unavailable');
        const data = await response.json();
        if (typeof data.csrf_token !== 'string' || !Array.isArray(data.password_requirements)
            || !data.password_requirements.every((item) => typeof item === 'string')) {
          throw new Error('Unexpected registration configuration');
        }
        if (active) setConfiguration(data);
      } catch {
        if (active) setSetupError(true);
      } finally {
        clearTimeout(timeout);
      }
    }
    prepare();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  useEffect(() => () => submission.current?.abort(), []);
  useEffect(() => {
    if (focusTarget) controls.current[focusTarget.name]?.focus();
  }, [focusTarget]);

  function change(name, value) {
    setValues((previous) => ({ ...previous, [name]: value }));
    setErrors((previous) => ({ ...previous, [name]: '', ...(name === 'password' ? { password_confirmation: '' } : {}) }));
    setMessage('');
  }

  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || !configuration || createdEmail) return;
    const nextErrors = Object.fromEntries(fields.map(({ name }) => [name, validate(name, values)]));
    setErrors(nextErrors);
    setMessage('');
    const firstInvalid = fields.find(({ name }) => nextErrors[name]);
    if (firstInvalid) {
      setMessage('Please check the highlighted fields.');
      setFocusTarget({ name: firstInvalid.name });
      return;
    }
    inFlight.current = true;
    setPending(true);
    const controller = new AbortController();
    submission.current = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': configuration.csrf_token },
        body: JSON.stringify(values),
        signal: controller.signal,
        cache: 'no-store',
      });
      if (response.status === 400) {
        const data = await response.json();
        const fieldErrors = {};
        for (const { name } of fields) {
          if (Array.isArray(data[name]) && data[name].every((item) => typeof item === 'string')) {
            fieldErrors[name] = data[name].join(' ');
          }
        }
        setErrors(fieldErrors);
        setMessage('We couldn’t create your account. Please check your details and try again.');
        setFocusTarget({ name: fields.find(({ name }) => fieldErrors[name])?.name || 'message' });
        return;
      }
      if (response.status === 403) {
        setConfiguration(null);
        setAttempt((value) => value + 1);
        setMessage('Your security check expired. Please try again once the form is ready.');
        setFocusTarget({ name: 'message' });
        return;
      }
      if (response.status !== 201) throw new Error('Registration failed');
      const data = await response.json();
      if (typeof data.email !== 'string' || !data.email) throw new Error('Unexpected registration response');
      setValues({ email: data.email, password: '', password_confirmation: '' });
      setVisible({});
      setCreatedEmail(data.email);
      setFocusTarget({ name: 'success' });
    } catch {
      setMessage('We couldn’t confirm your registration. Check your connection and try again. If the request reached the server, your account may already exist.');
      setFocusTarget({ name: 'message' });
    } finally {
      clearTimeout(timeout);
      submission.current = null;
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section className="registration-card" id="registration" aria-labelledby="registration-title">
      <p className="eyebrow">GET STARTED</p>
      <h2 id="registration-title">Create your account</h2>
      <p className="card-description">A first step toward a more connected campus.</p>
      {createdEmail ? (
        <div className="success-panel">
          <span className="success-icon" aria-hidden="true">✓</span>
          <h3 tabIndex="-1" ref={(node) => { controls.current.success = node; }}>Your account is ready</h3>
          <p>Registered as <strong>{createdEmail}</strong>.</p>
          <p>You haven’t been signed in. Sign-in will be available in a future update.</p>
        </div>
      ) : (
        <form onSubmit={submit} noValidate aria-busy={pending}>
          <p className="required-note">All fields are required.</p>
          {fields.map(({ name, label, autoComplete }) => (
            <div className="form-field" key={name}>
              <label htmlFor={name}>{label}</label>
              <div className="input-wrap">
                <input
                  ref={(node) => { controls.current[name] = node; }}
                  id={name} name={name} type={name === 'email' ? 'email' : visible[name] ? 'text' : 'password'}
                  autoComplete={autoComplete} autoCapitalize="none" spellCheck={false} required
                  value={values[name]} readOnly={pending}
                  aria-invalid={Boolean(errors[name])}
                  aria-describedby={`${name}-error${name === 'password' ? ' password-requirements' : ''}`}
                  onChange={(event) => change(name, event.target.value)}
                  onBlur={() => { if (!pending) setErrors((previous) => ({ ...previous, [name]: validate(name, values) })); }}
                />
                {name !== 'email' && (
                  <button className="visibility-toggle" type="button" aria-label={`${visible[name] ? 'Hide' : 'Show'} ${label.toLowerCase()}`}
                    aria-controls={name} aria-pressed={Boolean(visible[name])}
                    onClick={() => setVisible((previous) => ({ ...previous, [name]: !previous[name] }))}>
                    <EyeIcon visible={visible[name]} />
                  </button>
                )}
              </div>
              <p className="field-error" id={`${name}-error`} aria-live="polite">{errors[name] || '\u00a0'}</p>
              {name === 'password' && (
                <div className="password-requirements" id="password-requirements">
                  {configuration ? <><ul>{configuration.password_requirements.map((text) => <li key={text}>{text}</li>)}</ul>
                    <p>Use no more than 128 characters.</p></> : <p>Loading password requirements…</p>}
                </div>
              )}
            </div>
          ))}
          {setupError && <div className="setup-error" role="alert">
            <p>Registration is unavailable. Check your connection and try again.</p>
            <button type="button" className="secondary-button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
          </div>}
          <div className="form-message" ref={(node) => { controls.current.message = node; }} tabIndex="-1" role="alert">{message}</div>
          <button className="submit-button" type="submit" disabled={pending || !configuration}>
            <span className={`button-indicator ${pending ? 'loading-indicator' : ''}`} aria-hidden="true">{pending ? '' : '↗'}</span>
            {pending ? 'Creating account…' : 'Create account'}
          </button>
          <p className="form-note">Creating an account won’t sign you in automatically.</p>
        </form>
      )}
      <p className="sr-only" role="status">{createdEmail ? 'Account created successfully. You are not signed in.' : pending ? 'Creating account…' : ''}</p>
    </section>
  );
}
