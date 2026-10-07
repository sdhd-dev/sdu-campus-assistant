import { useState } from 'react';
import AuthPanel from './AuthPanel.jsx';
import CampusPhoto from './campus/CampusPhoto.jsx';
import ServiceStatus from './ServiceStatus.jsx';
import { DEFAULT_VIEW, viewpointFor } from './campus/viewpoints.js';
import useCalmMotion from './campus/useCalmMotion.js';

export default function App() {
  // The photograph lives here, beside the shell, so moving between login,
  // registration, and the profile only re-frames it.
  const [view, setView] = useState(
    () => (window.location.hash === '#login' ? 'login' : 'register'),
  );
  const calm = useCalmMotion();
  // The caption names where the camera actually is, including when it is parked.
  const place = viewpointFor(calm ? DEFAULT_VIEW : view);

  return (
    <>
      <CampusPhoto view={view} />
      <div className="page-shell">
        <a className="skip-link" href="#authentication">Skip to account</a>
        <header className="site-header">
          <a className="brand" href="#authentication">
            <span className="brand-plate">
              <img
                className="brand-logo"
                src="/brand/sdu-university-logo.svg"
                alt="SDU University"
                width="54"
                height="54"
              />
            </span>
            <span className="brand-name">
              Campus Assistant
              <span>University team project</span>
            </span>
          </a>
          <a className="status-link" href="#status-title">
            Service status<span className="status-link-arrow" aria-hidden="true">↓</span>
          </a>
        </header>
        <main>
          <AuthPanel onView={setView} />
          <p className="viewpoint" key={place.place}>
            <span className="viewpoint-place">{place.place}</span>
            <span className="viewpoint-detail">{place.detail}</span>
          </p>
        </main>
        <footer className="site-footer">

          <ServiceStatus />
        </footer>
      </div>
    </>
  );
}
