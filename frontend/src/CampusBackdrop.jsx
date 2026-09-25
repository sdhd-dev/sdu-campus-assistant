// A quiet campus skyline drawn once as plain SVG shapes: no images, fonts, or motion.
const FAR_BUILDINGS = [
  { x: 46, y: 250, width: 188, height: 180, windows: 4, rows: 3 },
  { x: 258, y: 296, width: 126, height: 134, windows: 3, rows: 2 },
  { x: 1046, y: 268, width: 206, height: 162, windows: 5, rows: 2 },
  { x: 1274, y: 306, width: 120, height: 124, windows: 3, rows: 2 },
];
const TREES = [
  { x: 240, size: 78 }, { x: 406, size: 58 }, { x: 1016, size: 64 },
  { x: 1256, size: 84 }, { x: 1418, size: 54 },
];
const GROUND = 430;

function ArchWindow({ x, y, width, height }) {
  const radius = width / 2;
  return <path d={`M${x} ${y + height}V${y + radius}a${radius} ${radius} 0 0 1 ${width} 0v${height - radius}Z`} />;
}

function WindowGrid({ x, y, width, height, windows, rows }) {
  const stepX = width / windows;
  const stepY = height / (rows + 0.6);
  const paneWidth = Math.min(stepX * 0.44, 15);
  return Array.from({ length: rows }, (_, row) => (
    Array.from({ length: windows }, (_, column) => (
      <ArchWindow
        key={`${row}-${column}`}
        x={x + stepX * (column + 0.5) - paneWidth / 2}
        y={y + stepY * (row + 0.55)}
        width={paneWidth}
        height={stepY * 0.62}
      />
    ))
  ));
}

function Tree({ x, size }) {
  return (
    <g>
      <rect x={x - size * 0.05} y={GROUND - size * 0.95} width={size * 0.1} height={size * 0.95} rx={size * 0.04} />
      <circle cx={x} cy={GROUND - size * 1.02} r={size * 0.42} />
      <circle cx={x - size * 0.31} cy={GROUND - size * 0.8} r={size * 0.29} />
      <circle cx={x + size * 0.33} cy={GROUND - size * 0.82} r={size * 0.27} />
    </g>
  );
}

export default function CampusBackdrop() {
  return (
    <div className="campus-backdrop" aria-hidden="true">
      <div className="backdrop-glow" />
      <svg
        className="backdrop-skyline"
        viewBox="0 0 1440 460"
        preserveAspectRatio="xMidYMax slice"
        focusable="false"
        role="presentation"
      >
        <g className="skyline-far">
          {FAR_BUILDINGS.map((building) => (
            <g key={building.x}>
              <rect x={building.x} y={building.y} width={building.width} height={building.height} rx="4" />
              <rect x={building.x - 8} y={building.y - 10} width={building.width + 16} height="12" rx="3" />
              <g className="skyline-windows"><WindowGrid {...building} /></g>
            </g>
          ))}
        </g>

        <g className="skyline-mid">
          {/* Clock tower */}
          <rect x="694" y="150" width="88" height="280" rx="4" />
          <path d="M686 150 738 96l52 54Z" />
          <rect x="726" y="76" width="24" height="24" rx="3" />
          <circle className="tower-clock" cx="738" cy="204" r="21" />
          <g className="skyline-windows">
            <ArchWindow x="724" y="256" width="28" height="52" />
            <ArchWindow x="724" y="334" width="28" height="52" />
          </g>

          {/* Main hall with a colonnade */}
          <rect x="470" y="288" width="196" height="142" rx="4" />
          <path d="M462 288 568 232l106 56Z" />
          <rect x="810" y="272" width="212" height="158" rx="4" />
          <path d="M802 272 916 216l114 56Z" />
          <g className="skyline-windows">
            <WindowGrid x={470} y={288} width={196} height={142} windows={5} rows={2} />
            <WindowGrid x={810} y={272} width={212} height={158} windows={5} rows={2} />
          </g>
        </g>

        <g className="skyline-near">
          {TREES.map((tree) => <Tree key={tree.x} {...tree} />)}
          <rect x="0" y={GROUND} width="1440" height="30" />
          {/* Pathway lamps along the walkway */}
          {[352, 620, 900, 1180].map((x) => (
            <g key={x} className="skyline-lamp">
              <rect x={x - 1.5} y={GROUND - 54} width="3" height="54" />
              <circle cx={x} cy={GROUND - 58} r="5" />
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}
