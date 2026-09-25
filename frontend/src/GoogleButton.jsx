import { useEffect, useRef, useState } from 'react';
import { authRequest } from './auth.js';

const SCRIPT = 'https://accounts.google.com/gsi/client';
let loader = null;

function loadGoogle() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google);
  loader ??= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => (window.google?.accounts?.id
      ? resolve(window.google) : reject(new Error('Google unavailable')));
    script.onerror = () => {
      loader = null;
      script.remove();
      reject(new Error('Google unavailable'));
    };
    document.head.append(script);
  });
  return loader;
}

// Renders Google's own button. The ID token it hands back is only a claim:
// the server verifies it with Google, against this session's nonce, and decides what it means.
// Renders nothing when the server has no Google client ID configured.
export default function GoogleButton({ onCredential, text = 'continue_with', separated = false }) {
  const target = useRef(null);
  const handler = useRef(onCredential);
  const [state, setState] = useState('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => { handler.current = onCredential; }, [onCredential]);

  useEffect(() => {
    const controller = new AbortController();
    setState('loading');
    authRequest('google', { signal: controller.signal }).then(async ({ response, data }) => {
      if (!response.ok) throw new Error('Unavailable');
      if (!data.client_id) {
        if (!controller.signal.aborted) setState('hidden');
        return;
      }
      const google = await loadGoogle();
      if (controller.signal.aborted || !target.current) return;
      google.accounts.id.initialize({
        client_id: data.client_id,
        nonce: data.nonce,
        ux_mode: 'popup',
        callback: ({ credential }) => handler.current(credential),
      });
      google.accounts.id.renderButton(target.current, {
        theme: 'outline', size: 'large', shape: 'pill', text, logo_alignment: 'left',
        width: Math.min(400, Math.max(200, target.current.offsetWidth || 320)),
      });
      setState('ready');
    }).catch(() => { if (!controller.signal.aborted) setState('error'); });
    return () => controller.abort();
  }, [attempt, text]);

  if (state === 'hidden') return null;
  return (
    <div className="google-sign-in">
      {separated && <div className="divider" aria-hidden="true"><span>or</span></div>}
      {/* Google's script owns this node's children; React never renders into it. */}
      <div className="google-button" ref={target} aria-busy={state === 'loading'} />
      {state === 'error' && (
        <p className="google-error" role="alert">
          Google sign-in didn’t load.{' '}
          <button type="button" className="secondary-button"
            onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </p>
      )}
    </div>
  );
}
