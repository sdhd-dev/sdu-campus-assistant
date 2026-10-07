// Geometry and labels imported from the approved sdu-campus-map.html SVG.
// Context blocks A–C are visual context, not a frontend room inventory.
export const MAP_BLOCKS = 'ABCDEFGHI'.split('');
export const MAP_ENTRANCES = ['MAIN', 'G', 'I'];
export default function CampusMap({ block, entrance, barrel, onSelect }) {
  function activate(event, type, code) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(type, code);
    }
  }
  return (
<svg viewBox="0 0 600 1100" role="group" aria-label="Schematic campus map. Select a block or entrance." className="campus-map-svg">
 <path className="corridor" d="M310 25H390V135L455 215 395 265V315L445 390 400 435H390V640L410 695V885L460 980 420 1035H335L295 985H155V925H310Z"/>
 <g data-block="I" role="button" tabIndex={0} aria-label="Block I" aria-pressed={block === 'I'}
    onClick={() => onSelect('block', 'I')} onKeyDown={event => activate(event, 'block', 'I')}>
    <path className={`wing${block === 'I' ? ' selected' : ''}`} d="M160 40L335 25V115H160V82H305V60L160 73Z"/><text className="block-name" x="25" y="78">Block I</text><path className="partition" d="M188 38V69M217 36V65M248 33V63M277 30V61M188 82V115M217 82V115M247 82V115M277 82V115"/></g>
 <path className="wing" d="M355 25H390V135H355Z"/>
 <g data-block="H" role="button" tabIndex={0} aria-label="Block H" aria-pressed={block === 'H'}
    onClick={() => onSelect('block', 'H')} onKeyDown={event => activate(event, 'block', 'H')}>
    <path className={`wing${block === 'H' ? ' selected' : ''}`} d="M160 190L310 175V115H335V255H160V221H310V206L160 221Z"/><text className="block-name" x="25" y="220">Block H</text><path className="partition" d="M190 187V218M220 184V215M250 181V211M280 178V208M190 221V255M220 221V255M250 221V255M280 221V255"/></g>
 <path className="wing" d="M390 140L425 175 414 185 450 224 414 250 388 220 405 205 379 170Z"/>
 <circle className="corridor" cx="401" cy="207" r="18"/>
 <g data-block="G" role="button" tabIndex={0} aria-label="Block G" aria-pressed={block === 'G'}
    onClick={() => onSelect('block', 'G')} onKeyDown={event => activate(event, 'block', 'G')}>
    <path className={`wing${block === 'G' ? ' selected' : ''}`} d="M160 335L310 320V292H335V415H160V381H310V351L160 369Z"/><text className="block-name" x="25" y="363">Block G</text><path className="partition" d="M190 332V365M220 329V360M250 326V357M280 323V353M190 381V415M220 381V415M250 381V415M280 381V415"/></g>
 <path className="wing" d="M310 267H335V310H310Z"/>
 <g data-block="C" role="button" tabIndex={0} aria-label="Block C" aria-pressed={block === 'C'}
    onClick={() => onSelect('block', 'C')} onKeyDown={event => activate(event, 'block', 'C')}>
    <path className={`wing${block === 'C' ? ' selected' : ''}`} d="M397 925L428 958 451 983 432 1007 411 987 389 1005 363 977Z"/><text x="460" y="969">Block C</text></g>
 <path className="wing" d="M401 398L440 422 450 411 468 429 430 460 395 423Z"/>
 <g data-block="F" role="button" tabIndex={0} aria-label="Block F" aria-pressed={block === 'F'}
    onClick={() => onSelect('block', 'F')} onKeyDown={event => activate(event, 'block', 'F')}>
    <path className={`wing${block === 'F' ? ' selected' : ''}`} d="M160 495L335 480V575H160V542H310V517L160 531Z"/><text className="block-name" x="25" y="529">Block F</text><path className="partition" d="M190 493V528M220 490V524M250 487V522M280 485V518M190 542V575M220 542V575M250 542V575M280 542V575"/></g>
 <path className="wing" d="M390 470H487V504L451 547V602H431V652L442 667 428 684H407V659H390Z"/>
 <text x="402" y="538">Canteen</text><path className="partition" d="M390 605H431"/>
 <g data-block="E" role="button" tabIndex={0} aria-label="Block E" aria-pressed={block === 'E'}
    onClick={() => onSelect('block', 'E')} onKeyDown={event => activate(event, 'block', 'E')}>
    <path className={`wing${block === 'E' ? ' selected' : ''}`} d="M160 665L335 650V740H160V708H310V686L160 700Z"/><text className="block-name" x="25" y="703">Block E</text><path className="partition" d="M190 662V697M220 660V693M250 657V690M280 655V686M190 708V740M220 708V740M250 708V740M280 708V740"/></g>
 <path className="wing" d="M310 760H335V807H310Z"/>
 <g data-block="D" role="button" tabIndex={0} aria-label="Block D" aria-pressed={block === 'D'}
    onClick={() => onSelect('block', 'D')} onKeyDown={event => activate(event, 'block', 'D')}>
    <path className={`wing${block === 'D' ? ' selected' : ''}`} d="M160 825L335 810V900H160V868H310V846L160 860Z"/><text className="block-name" x="25" y="861">Block D</text><path className="partition" d="M190 822V856M220 820V853M250 817V850M280 815V847M190 868V900M220 868V900M250 868V900M280 868V900"/></g>
 <circle className={`barrel${barrel === 'D' ? ' selected' : ''}`} data-barrel="D" cx="381" cy="696" r="27"/><text x="424" y="702">Barrel D</text>
 <circle className={`barrel${barrel === 'C' ? ' selected' : ''}`} data-barrel="C" cx="407" cy="775" r="31"/><text x="453" y="781">Barrel C</text>
 <circle className={`barrel${barrel === 'B' ? ' selected' : ''}`} data-barrel="B" cx="381" cy="844" r="27"/><text x="424" y="850">Barrel B</text>
 <circle className={`barrel${barrel === 'A' ? ' selected' : ''}`} data-barrel="A" cx="407" cy="906" r="31"/><text x="453" y="912">Barrel A</text>
 <g data-block="A" role="button" tabIndex={0} aria-label="Block A" aria-pressed={block === 'A'}
    onClick={() => onSelect('block', 'A')} onKeyDown={event => activate(event, 'block', 'A')}>
    <path className={`wing${block === 'A' ? ' selected' : ''}`} d="M55 939H75V925H134V940H154V1020H55Z"/><text x="65" y="981">Block A</text></g>
 <path className="wing" d="M222 930H267V947H290V968H220Z"/><path className="partition" d="M237 930V947M251 930V947M239 948V968M263 948V968"/>
 <path className="partition" d="M316 907V920H332V933H316V946H332V959H316"/>
 <g data-block="B" role="button" tabIndex={0} aria-label="Block B" aria-pressed={block === 'B'}
    onClick={() => onSelect('block', 'B')} onKeyDown={event => activate(event, 'block', 'B')}>
    <path className={`wing${block === 'B' ? ' selected' : ''}`} d="M222 1023H286V1010H308V1043H335V1063H222Z"/><text x="235" y="1046">Block B</text><text x="219" y="1087">Library area *</text></g>
 <circle className="wing" cx="375" cy="1007" r="23"/>
 <path className="partition" d="M175 932H210M175 947H210M175 962H210M175 977H210M333 998L353 1018M338 993L358 1013"/>
 <g data-entry="I" role="button" tabIndex={0} aria-label="Entrance I" aria-pressed={entrance === 'I'}
    onClick={() => onSelect('entrance', 'I')} onKeyDown={event => activate(event, 'entrance', 'I')}>
    <circle className={`entry${entrance === 'I' ? ' selected' : ''}`} cx="390" cy="43" r="9"/><text x="412" y="49">Entrance I *</text></g>
 <g data-entry="G" role="button" tabIndex={0} aria-label="Entrance G" aria-pressed={entrance === 'G'}
    onClick={() => onSelect('entrance', 'G')} onKeyDown={event => activate(event, 'entrance', 'G')}>
    <circle className={`entry${entrance === 'G' ? ' selected' : ''}`} cx="390" cy="280" r="9"/><text x="412" y="286">Entrance G</text></g>
 <g data-entry="MAIN" role="button" tabIndex={0} aria-label="Main entrance" aria-pressed={entrance === 'MAIN'}
    onClick={() => onSelect('entrance', 'MAIN')} onKeyDown={event => activate(event, 'entrance', 'MAIN')}>
    <circle className={`entry${entrance === 'MAIN' ? ' selected' : ''}`} cx="434" cy="1020" r="10"/><text x="383" y="1067">Main entrance</text></g>
 </svg>
  );
}
