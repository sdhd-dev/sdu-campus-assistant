import { useEffect, useState } from 'react';

export default function App() {
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
    loading: 'Checking backend connection…',
    ok: 'Backend and database are online.',
    error: 'Cannot reach a healthy backend. Check that Django and PostgreSQL are running, then try again.',
  };

  return (
    <main>
      <p className="eyebrow">SDU · UNIVERSITY TEAM PROJECT</p>
      <h1>SDU Campus Assistant</h1>
      <p className="intro">
        A foundation for finding your way around campus, discovering university
        services, and keeping up with student schedules.
      </p>
      <section className="status-card" aria-labelledby="status-title">
        <h2 id="status-title">Service status</h2>
        <p role="status" aria-live="polite" className={`status ${status}`}>
          {statusText[status]}
        </p>
        <button disabled={status === 'loading'} onClick={() => setAttempt((value) => value + 1)}>
          {status === 'loading' ? 'Checking…' : 'Check again'}
        </button>
      </section>
      <p className="footnote">US-01 · Project &amp; database setup</p>
    </main>
  );
}
