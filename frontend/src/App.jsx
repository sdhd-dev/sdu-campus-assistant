import { useState } from 'react';
import AuthPanel from './AuthPanel.jsx';
import CampusPhoto from './campus/CampusPhoto.jsx';

export default function App() {
  // The photograph lives here, beside the shell, so moving between login,
  // registration, and the profile only re-frames it.
  const [view, setView] = useState(
    () => (window.location.hash === '#login' ? 'login' : 'register'),
  );

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
        </header>
        <main>
          <AuthPanel onView={setView} />
        </main>
      </div>
    </>
  );
}
