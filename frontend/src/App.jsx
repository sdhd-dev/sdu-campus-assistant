import AuthPanel from './AuthPanel.jsx';
import CampusBackdrop from './CampusBackdrop.jsx';
import ServiceStatus from './ServiceStatus.jsx';

export default function App() {
  return (
    <>
      {/* A sibling of the shell, so no page content depends on a negative z-index. */}
      <CampusBackdrop />
      <div className="page-shell">
        <a className="skip-link" href="#authentication">Skip to account</a>
        <header className="site-header">
          <a className="brand" href="#authentication">
            <span className="brand-mark" aria-hidden="true">SDU</span>
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
          <AuthPanel />
        </main>
        <footer className="site-footer">
          <div className="footer-brand">
            <p>SDU Campus Assistant</p>
            <p className="footer-note">
              Sprint 1: accounts and profiles. Campus features are in progress.
            </p>
          </div>
          <ServiceStatus />
        </footer>
      </div>
    </>
  );
}
