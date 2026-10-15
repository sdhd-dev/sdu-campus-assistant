import { useEffect, useRef, useState } from 'react';
import { DEFAULT_VIEW, viewpointFor } from './viewpoints.js';
import useCalmMotion from './useCalmMotion.js';

/*
  One photograph of the SDU campus, loaded once and kept for the whole session.
  Navigation never swaps or reloads it: it only re-frames the same picture, so
  login, registration and the profile are three crops of one place.

  This is a photographic move — a push and a pan across a still image — not a
  3D camera. Nothing here reveals a face of a building the photograph does not
  already show, and the image is never cut apart into fake depth layers.
*/
export default function CampusPhoto({ view }) {
  const calm = useCalmMotion();
  const frame = viewpointFor(calm ? DEFAULT_VIEW : view);
  const parallax = useRef(null);
  const [state, setState] = useState('loading');

  // Gentle pointer parallax, desktop only, and never against reduced motion.
  useEffect(() => {
    if (calm || window.matchMedia('(pointer: coarse)').matches) return undefined;
    const node = parallax.current;
    let pending = null;
    let queued = 0;

    function apply() {
      queued = 0;
      if (node && pending) node.style.transform = `translate3d(${pending.x}%, ${pending.y}%, 0)`;
    }
    function onMove(event) {
      if (document.hidden) return;
      pending = {
        x: ((event.clientX / window.innerWidth - 0.5) * -1.6).toFixed(3),
        y: ((event.clientY / window.innerHeight - 0.5) * -1).toFixed(3),
      };
      // At most one write per frame; nothing runs while the pointer is still.
      if (!queued) queued = requestAnimationFrame(apply);
    }
    function rest() {
      pending = { x: 0, y: 0 };
      if (!queued) queued = requestAnimationFrame(apply);
    }

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerleave', rest);
    document.addEventListener('visibilitychange', rest);
    return () => {
      if (queued) cancelAnimationFrame(queued);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerleave', rest);
      document.removeEventListener('visibilitychange', rest);
      if (node) node.style.transform = '';
    };
  }, [calm]);

  return (
    <div className="campus-stage" data-state={state} aria-hidden="true">
      <div className="campus-parallax" ref={parallax}>
        <div
          className="campus-frame"
          style={{ transform: `translate(${frame.x}%, ${frame.y}%) scale(${frame.scale})` }}
        >
          <img
            className="campus-photo"
            src="/campus/sdu-campus-1800.jpg"
            srcSet="/campus/sdu-campus-1200.webp 1200w, /campus/sdu-campus-1800.webp 1800w, /campus/sdu-campus-2560.webp 2560w"
            sizes="180vw"
            alt=""
            decoding="async"
            fetchPriority="low"
            onLoad={() => setState('ready')}
            onError={() => setState('failed')}
          />
        </div>
      </div>
      <div className="campus-grade" />
    </div>
  );
}
