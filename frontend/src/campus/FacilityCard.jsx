import PhotoGallery from './PhotoGallery.jsx';
import ServiceDetails from './ServiceDetails.jsx';
import './facility-card.css';

export default function FacilityCard({ place }) {
  return <article className="facility-card" aria-label={place.name}>
    <h2>{place.name}</h2>
    <p className="facility-location">{place.location || (place.block ? `Block ${place.block.code}` : 'Location not confirmed')}
      {place.floor !== null && ` · ${place.floor === 0 ? 'Basement' : `Floor ${place.floor}`}`}</p>
    <p className="facility-category">{place.is_service ? 'University service' : place.category === 'AUDITORIUM' ? 'Auditorium' : place.category === 'LIBRARY' ? 'Library' : 'Campus facility'}</p>
    <PhotoGallery place={place} />
    <p className="facility-description">{place.description}</p>
    {place.details?.length > 0 && <ul className="facility-details">{place.details.map(detail => <li key={detail}>{detail}</li>)}</ul>}
    {place.map_note && <><p className="facility-map-note facility-note-desktop">{place.map_note}</p><details className="facility-note-mobile"><summary>Approximate location · Details</summary><p>{place.map_note}</p></details></>}
    {place.is_service ? <ServiceDetails place={place} /> : place.opening_hours && <p>Opening hours: {place.opening_hours}</p>}
    {place.map_available && <a className="map-result-link" href={`#/map?${new URLSearchParams({ type: 'place', id: String(place.id) })}`}>Show on map</a>}
    {place.is_service && !place.map_available && <p>Location landmark: {place.location || 'Not provided'}. Exact map point: Not provided.</p>}
  </article>;
}
