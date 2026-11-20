const doors = { LEFT: 'Left door', CENTRAL: 'Central door', RIGHT: 'Right door', HALL: 'Hall' };

export function OfficeLocation({ office }) {
  return <>
    <p className="search-location">{office.source_room}
      {office.room && ` · Block ${office.room.block} · ${office.room.floor === 0 ? 'Basement' : `Floor ${office.room.floor}`}`}
      {office.door && ` · ${doors[office.door] || office.door}`}</p>
    <p>{office.faculty.name}{office.faculty.code !== office.faculty.name && ` (${office.faculty.code})`}</p>
    {office.alternative_label && <p>Alternative source label: {office.alternative_label} (relationship requires confirmation).</p>}
    {office.map_available && office.room ? <a className="map-result-link" href={`#/map?type=room&id=${office.room.id}`}>Show on map</a>
      : <p>Map location not recorded.</p>}
  </>;
}

export default function PersonCard({ person }) {
  return <article aria-label={person.name}>
    <h2>{person.title && `${person.title} `}{person.name}</h2>
    <p>{({ TEACHER: 'Teacher', STAFF: 'Staff', UNKNOWN: 'Staff directory · Role not confirmed' })[person.role] || 'Role not confirmed'}</p>
    {person.offices.length ? person.offices.map(office => <div className="person-office" key={office.id}><OfficeLocation office={office} /></div>)
      : <p>Office and map location not recorded.</p>}
  </article>;
}

export function RoomPeople({ people }) {
  if (!people?.length) return null;
  return <section className="room-people" aria-label="People listed for this office">
    <h3>People listed for this office</h3>
    <ul>{people.map(person => <li key={`${person.id}-${person.source_room}`}>
      {person.title && `${person.title} `}{person.name} · {person.faculty.code}
      {person.door && ` · ${doors[person.door] || person.door}`}
      {person.alternative_label && ` · Alternative source label: ${person.alternative_label}`}
    </li>)}</ul>
  </section>;
}
