import { useEffect, useState } from 'react';

export default function ServiceStatus() {
  const [status, setStatus] = useState('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 8000);
    setStatus('loading');

    async function checkBackend() {
      try {
        const response = await fetch('/api/health/', {
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!response.ok) throw new Error('Backend unavailable');
        const data = await response.json();
        if (data.status !== 'ok') throw new Error('Unexpected health response');
        if (active) setStatus('ok');
      } catch {
        if (active) setStatus('error');
      } finally {
        clearTimeout(timeout);
      }
    }

    checkBackend();
    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  const statusText = {
    loading: 'Checking service…',
    ok: 'Service available',
    error: 'Service temporarily unavailable',
  };

  return (
    <section className="status-card" aria-labelledby="status-title" tabIndex="-1">
      <h2 id="status-title">
        <span className={`status-dot ${status}`} aria-hidden="true" />Service status
      </h2>
      <p role="status" aria-live="polite" className={`status ${status}`}>
        {statusText[status]}
      </p>
      <button disabled={status === 'loading'} onClick={() => setAttempt((value) => value + 1)}>
        {status === 'loading' ? 'Checking…' : 'Check again'}
      </button>
    </section>
  );
}
