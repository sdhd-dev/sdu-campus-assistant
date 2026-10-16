import { useEffect, useRef, useState } from 'react';

export default function PhotoGallery({ place }) {
  const [failed, setFailed] = useState([]);
  const [selected, setSelected] = useState(null);
  const dialog = useRef(null);
  const photos = [...(place.photo ? [{ path: place.photo, alt: place.photo_alt }] : []), ...(place.extra_photos || [])];
  useEffect(() => { setFailed([]); setSelected(null); dialog.current?.close(); }, [place.id, place.photo]);
  if (!photos.length) return place.is_service ? <p>Photos: Not provided</p> : null;
  return <>
    <div className={`facility-gallery${place.is_service ? ' service-gallery' : ''}`}>
      {photos.map((photo, index) => failed.includes(photo.path) ? <p key={photo.path} role="status">Photo unavailable.</p> :
        <button key={photo.path} className="facility-photo-button" aria-label={`Open full photo of ${place.name}${index ? ` (${index + 1})` : ''}`}
          onClick={() => { setSelected(photo); dialog.current?.showModal(); }}>
          <img src={photo.path} alt={photo.alt} loading="lazy" onError={() => setFailed(v => [...v, photo.path])} />
          <span>{index ? 'View additional photo' : 'View full photo'}</span>
        </button>)}
    </div>
    <dialog ref={dialog} className="facility-photo-dialog" aria-label={`Full photo of ${place.name}`}>
      <button className="secondary-button" onClick={() => dialog.current.close()} autoFocus>Close photo</button>
      {selected && <img src={selected.path} alt={selected.alt} onError={() => { dialog.current.close(); setFailed(v => [...v, selected.path]); }} />}
    </dialog>
  </>;
}
