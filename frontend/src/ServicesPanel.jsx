import { useEffect, useRef, useState } from 'react';
import { apiRequest, SESSION_EXPIRED } from './auth.js';
import FacilityCard from './campus/FacilityCard.jsx';
import './search.css';
const dayNames = {MON:'Monday',TUE:'Tuesday',WED:'Wednesday',THU:'Thursday',FRI:'Friday',SAT:'Saturday',SUN:'Sunday'};
const weeklySummary = hours => Object.entries(hours || {}).map(([day,value]) =>
  `${dayNames[day] || day}: ${value.closed ? 'Closed' : `${value.opens}–${value.closes}`}`).join('; ');

export default function ServicesPanel({ hash, onSignedOut }) {
  const params = new URLSearchParams(hash.split('?')[1] || '');
  const slug = params.get('slug') || '';
  const query = params.get('q') || '';
  const [draft,setDraft] = useState(query);
  useEffect(()=>setDraft(query),[query]);
  const [state,setState] = useState({status:'loading'});
  const [attempt,setAttempt] = useState(0);
  const heading = useRef(null);
  useEffect(()=>{ heading.current?.focus(); },[slug]);
  useEffect(()=>{
    const controller = new AbortController();
    setState({status:'loading'});
    apiRequest('campus/services',{signal:controller.signal,query:slug ? new URLSearchParams({slug}) : undefined})
      .then(({response,data})=>{
        if(controller.signal.aborted)return;
        if(response.status===401){onSignedOut(SESSION_EXPIRED);return;}
        if(!response.ok)throw new Error(response.status===404 ? 'Service not found.' : 'Please try again.');
        if(slug ? !data?.is_service : !Array.isArray(data?.services))throw new Error('Invalid service response.');
        setState({status:'ready',data});
      }).catch(error=>{if(!controller.signal.aborted)setState({status:'error',message:error.message});});
    return ()=>controller.abort();
  },[slug,attempt,onSignedOut]);
  const normalize = value => String(value || '').normalize('NFKC').toLowerCase().replace(/[\s-]+/g,'');
  const matches = !slug && state.status === 'ready' ? state.data.services.filter(place =>
    [place.name, place.room_code, ...(place.aliases || [])].some(value=>normalize(value).includes(normalize(query)))) : [];
  const serviceLink = code => `#services?${new URLSearchParams({slug:code,...(query ? {q:query} : {})})}`;
  return <section className="panel home-panel search-panel" lang="en">
    <p className="eyebrow">University services</p>
    <h1 ref={heading} tabIndex="-1">{slug ? 'Service details' : 'Plan your campus visit'}</h1>
    {!slug && <p>Find service locations, published hours and contacts.</p>}
    {!slug && <form className="home-search" role="search" onSubmit={event=>{
      event.preventDefault();window.location.hash = draft.trim() ? `services?${new URLSearchParams({q:draft.trim()})}` : 'services';
    }}>
      <label className="sr-only" htmlFor="service-query">Service name or office number</label>
      <input id="service-query" type="search" value={draft} maxLength={80} onChange={event=>setDraft(event.target.value)}
        placeholder="SSC, Advising Desk or D109" autoComplete="off" />
      <button className="submit-button" type="submit">Search</button>
    </form>}
    <div aria-live="polite" aria-busy={state.status==='loading'}>
      {state.status==='loading' && <p role="status">Loading services…</p>}
      {state.status==='error' && <div role="alert"><p>Services unavailable. {state.message}</p><button className="secondary-button" onClick={()=>setAttempt(v=>v+1)}>Retry services</button></div>}
      {state.status==='ready' && (slug ? <FacilityCard place={state.data} /> : <>
        <p role="status">{matches.length ? `Services: ${matches.length}` : query ? 'No services found. Try a service name or office number.' : 'No services have been added yet.'}</p>
        {query && <a href="#services">Clear search</a>}
        <ul className="search-results">{matches.map(place=><li className="search-result service-summary" key={place.id}>
          <h2><a href={serviceLink(place.code)}>{place.name}</a></h2>
          {place.photo && <img className="service-summary-photo" src={place.photo} alt={place.photo_alt} loading="lazy" onError={e=>{e.currentTarget.hidden=true;}} />}
          <p>{place.location || 'Location: Not provided'}</p>
          <p>Opening hours: {place.opening_hours || weeklySummary(place.weekly_hours) || 'Not provided'}</p>
          <p>Working days: {place.working_days || 'Not provided'}</p>
          {place.document_collection_hours && <p>Document collection: {place.document_collection_hours}</p>}
          <a href={serviceLink(place.code)}>View details</a>
        </li>)}</ul>
      </>)}
    </div>
    <div className="panel-footer home-footer">{slug && <a href={query ? `#services?${new URLSearchParams({q:query})}` : '#services'}>← All services</a>}<a href="#home">← Back to home</a></div>
  </section>;
}
