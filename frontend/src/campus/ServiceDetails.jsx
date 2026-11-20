const days = {MON:'Monday',TUE:'Tuesday',WED:'Wednesday',THU:'Thursday',FRI:'Friday',SAT:'Saturday',SUN:'Sunday'};
export default function ServiceDetails({ place }) {
  const weekly = place.weekly_hours || {};
  return <div className="service-details">
    <h3>Plan your visit</h3>
    <dl>
      <dt>Opening hours</dt><dd>{place.opening_hours || 'Not provided'}</dd>
      <dt>Working days</dt><dd>{place.working_days || 'Not provided'}</dd>
      <dt>Lunch break</dt><dd>{place.lunch_break || 'Not provided'}</dd>
      <dt>Document collection</dt><dd>{place.document_collection_hours || 'Not provided'}</dd>
    </dl>
    {Object.keys(weekly).length > 0 && <><h3>Published weekly hours</h3><dl>
      {Object.entries(days).map(([day,label]) => <div key={day}><dt>{label}</dt>
        <dd>{!weekly[day] ? 'Not provided' : weekly[day].closed ? 'Closed' : `${weekly[day].opens}–${weekly[day].closes}`}</dd></div>)}
    </dl></>}
    {place.schedule_note && <p className="service-schedule-note">{place.schedule_note}</p>}
    <h3>Published contacts</h3>
    {place.contacts?.length ? <dl>{place.contacts.map(contact => <div key={contact.label+contact.value}><dt>{contact.label}</dt><dd>{contact.value}</dd></div>)}</dl> : <p>Not provided</p>}
    {place.service_staff?.length > 0 && <><h3>Staff</h3><ul>{place.service_staff.map(person => <li key={person.name}>{person.name} — {person.role}</li>)}</ul></>}
  </div>;
}
