export const SESSION_EXPIRED = 'Your session has expired. Please sign in again.';

// Session cookies stay in the browser; CSRF tokens live only in component state.
export async function apiRequest(path, { signal, timeout = 15000, ...options } = {}) {
  const deadline = AbortSignal.timeout(timeout);
  const response = await fetch(`/api/${path}/`, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store',
    signal: signal ? AbortSignal.any([signal, deadline]) : deadline,
  });
  const data = response.status === 204 ? null : await response.json();
  return { response, data };
}

export function authRequest(path, options) {
  return apiRequest(`auth/${path}`, options);
}

export function isSession(data) {
  return typeof data?.email === 'string' && Boolean(data.email)
    && typeof data.csrf_token === 'string' && Boolean(data.csrf_token);
}

// The server owns the list of affiliations; the page never invents a value.
export function isProfile(data) {
  return isSession(data)
    && typeof data.profile_type === 'string'
    && Array.isArray(data.profile_types) && data.profile_types.length > 0
    && data.profile_types.every((option) => typeof option?.value === 'string'
      && Boolean(option.value) && typeof option.label === 'string' && Boolean(option.label))
    && data.profile_types.some((option) => option.value === data.profile_type);
}

export function isSecurity(data) {
  return typeof data?.csrf_token === 'string' && Boolean(data.csrf_token)
    && ['google_available', 'google_linked', 'has_password', 'two_factor_enabled']
      .every((key) => typeof data[key] === 'boolean')
    && Number.isInteger(data.recovery_codes_remaining);
}

export function isVerification(data) {
  const text = (value) => value === null || (typeof value === 'string' && Boolean(value));
  return typeof data?.csrf_token === 'string' && Boolean(data.csrf_token)
    && [null, 'STUDENT', 'STAFF'].includes(data.verified_affiliation)
    && text(data.university_email) && text(data.verified_at) && text(data.pending_email)
    && Number.isInteger(data.resend_in) && data.resend_in >= 0
    && ['student_domains', 'staff_domains'].every((key) => Array.isArray(data[key])
      && data[key].every((domain) => typeof domain === 'string'));
}
