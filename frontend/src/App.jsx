import RegistrationForm from './RegistrationForm.jsx';
import ServiceStatus from './ServiceStatus.jsx';

export default function App() {
  return (
    <div className="page-shell">
      <a className="skip-link" href="#registration">Skip to registration</a>
      <header className="site-header">
        <span className="brand-mark" aria-hidden="true">SDU</span>
        <span className="brand-name">Campus Assistant<span>UNIVERSITY TEAM PROJECT</span></span>
        <a className="status-link" href="#status-title">Service status <span aria-hidden="true">↗</span></a>
      </header>
      <main className="registration-layout">
        <section className="introduction" aria-labelledby="project-title">
          <p className="eyebrow">YOUR CAMPUS. A LITTLE CLOSER.</p>
          <h1 id="project-title">Welcome to your<br className="desktop-break" /> campus community.</h1>
          <p className="intro">SDU Campus Assistant is taking shape: a place to find your way,
            discover university services, and keep up with student schedules.</p>
          <p className="intro-note">Start by creating your account.</p>
          <div className="project-note"><span className="note-line" aria-hidden="true" />
            <p>Built for everyday campus life.<br /><span>Made by a university team.</span></p>
          </div>
        </section>
        <RegistrationForm />
      </main>
      <footer className="site-footer">
        <p>SDU Campus Assistant <span>· A university team project</span></p>
        <ServiceStatus />
      </footer>
    </div>
  );
}
