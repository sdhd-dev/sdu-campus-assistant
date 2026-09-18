// Session cookies stay in the browser; CSRF tokens live only in component state.
export async function authRequest(path, { signal, ...options } = {}) {
  const response = await fetch(`/api/auth/${path}/`, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store',
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  });
  const data = response.status === 204 ? null : await response.json();
  return { response, data };
}

export function isSession(data) {
  return typeof data?.email === 'string' && Boolean(data.email)
    && typeof data.csrf_token === 'string' && Boolean(data.csrf_token);
}
