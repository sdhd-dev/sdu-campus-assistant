import { useEffect, useRef, useState } from 'react';
import './facility-card.css';

export default function FacilityCard({ place }) {
  const [failed, setFailed] = useState(false);
  const dialog = useRef(null);
  useEffect(() => { setFailed(false); dialog.current?.close(); }, [place.id, place.photo]);
  return <article className="facility-card" aria-label={place.name}>
    <h2>{place.name}</h2>
    <p className="facility-location">{place.location || (place.block ? `Block ${place.block.code}` : 'Location not confirmed')}
      {place.floor !== null && ` · ${place.floor === 0 ? 'Basement' : `Floor ${place.floor}`}`}</p>
    <p className="facility-category">{place.category === 'AUDITORIUM' ? 'Auditorium' : place.category === 'LIBRARY' ? 'Library' : 'Campus facility'}</p>
    {place.photo && !failed ? <button className="facility-photo-button" aria-label={`Open full photo of ${place.name}`} onClick={() => dialog.current?.showModal()}>
      <img src={place.photo} alt={place.photo_alt} loading="lazy" onError={() => setFailed(true)} />
      <span>View full photo</span>
    </button> : place.photo && <p role="status">Photo unavailable.</p>}
    <p className="facility-description">{place.description}</p>
    {place.details?.length > 0 && <ul className="facility-details">{place.details.map(detail => <li key={detail}>{detail}</li>)}</ul>}
    {place.map_note && <><p className="facility-map-note facility-note-desktop">{place.map_note}</p><details className="facility-note-mobile"><summary>Approximate location · Details</summary><p>{place.map_note}</p></details></>}
    {place.opening_hours && <p>Opening hours: {place.opening_hours}</p>}
    {place.map_available && <a className="map-result-link" href={`#/map?${new URLSearchParams({ type: 'place', id: String(place.id) })}`}>Show on map</a>}
    {place.photo && !failed && <dialog ref={dialog} className="facility-photo-dialog" aria-label={`Full photo of ${place.name}`}>
      <button className="secondary-button" onClick={() => dialog.current.close()} autoFocus>Close photo</button>
      <img src={place.photo} alt={place.photo_alt} loading="lazy" onError={() => { dialog.current.close(); setFailed(true); }} />
    </dialog>}
  </article>;
}
