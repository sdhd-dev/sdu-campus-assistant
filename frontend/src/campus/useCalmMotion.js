import { useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

// Reduced motion keeps one composed viewpoint for the whole session instead of
// cutting between camera positions, which would be its own kind of motion.
export default function useCalmMotion() {
  const [calm, setCalm] = useState(() => window.matchMedia(QUERY).matches);
  useEffect(() => {
    const query = window.matchMedia(QUERY);
    const update = () => setCalm(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return calm;
}
