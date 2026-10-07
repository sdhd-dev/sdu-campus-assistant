import './place-details.css';

export function FacultyInfo({ block }) {
  if (!block) return null;
  if (!block.faculty_name) return <p className="faculty-name">Faculty not confirmed</p>;
  return <div className="faculty-info">
    <p className="faculty-name">{block.faculty_name}</p>
    {block.faculty_source && <p className="faculty-source">{block.faculty_source}</p>}
  </div>;
}

export function RoomDescription({ place }) {
  if (!['room', 'place', 'entrance'].includes(place.type) || !place.description) return null;
  // Only the generated ordinary-room placeholder is omitted. Barrel and manual
  // descriptions remain visible as full text in both Search and Campus Map.
  if (place.kind !== 'BARREL' && place.description ===
      'Предварительная запись по нумерации; проверить при сборе данных кампуса.') return null;
  return <p className="room-description">{place.description}</p>;
}
