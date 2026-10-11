// Stylised Abu Dhabi corniche at dusk: an illustrative silhouette, not a map.

// Side-view figures facing right, feet at y = 0, about 40 units tall.
// Each part is a separate path so the backlit rim can outline the whole silhouette.
const MAN_WALKING = [
  // ghutra framing the face and falling behind the shoulders
  "M3.3 -37.4 C2.4 -39.9 -2.3 -39.9 -3.1 -36.6 C-3.7 -33 -4.7 -29 -5.4 -25.2 L-2 -26.4 C-1 -29 0 -31 1.3 -32.3 L2.6 -33 C2.4 -34.5 2.7 -36 3.3 -37.4 Z",
  // face
  "M1.4 -36.6 C2.6 -36.7 3.4 -35.7 3.4 -34.4 C3.4 -33.4 3 -32.7 2.3 -32.4 L1.2 -32.6 Z",
  // kandura, hem opening with the stride
  "M-2.6 -31 C1.4 -31.7 4 -30.6 4.2 -27 L4.6 -14 L6.6 -1.6 L-5.6 -1.6 L-3.8 -14 C-4.4 -22 -4.2 -28 -2.6 -31 Z",
  // swinging arm
  "M0.4 -29.6 C2.8 -25.2 4.4 -21 5.8 -17.2 L4.3 -16.5 C3 -19.8 1.3 -24 -0.9 -28.2 Z",
  // sandals
  "M3.9 -1.9 L7.8 -0.7 L7.8 0 L3.5 0 Z",
  "M-5.2 -1.9 L-2.1 -0.5 L-2.1 0 L-5.8 0 Z",
];

const MAN_STANDING = [
  MAN_WALKING[0],
  MAN_WALKING[1],
  "M-2.6 -31 C1.4 -31.7 4 -30.6 4.2 -27 L4.4 -14 L4.4 -1.6 L-4.4 -1.6 L-3.9 -14 C-4.4 -22 -4.2 -28 -2.6 -31 Z",
  "M3.4 -1.9 L6.6 -0.7 L6.6 0 L3 0 Z",
];

const FALCON_ARM = [
  // forearm raised in front, gloved fist
  "M0.4 -29.4 C1.2 -25.8 1.8 -22.8 2.4 -21.1 L7.4 -21.6 L7.6 -19.6 L1.6 -19 C0.2 -22 -0.8 -25.4 -1.2 -28.6 Z",
  // hooded falcon perched on the fist
  "M6 -21.8 C5.2 -24.6 5.8 -27.8 7.6 -28.6 C8.6 -29 9.6 -28.4 9.7 -27.4 L10.8 -27 L9.7 -26.5 C9.9 -24.7 9.3 -22.7 8.3 -21.8 Z",
  "M6.3 -22 L5.4 -18.7 L6.9 -18.9 Z",
];

const WOMAN_WALKING = [
  // abaya flowing back with the stride
  "M-3 -29.6 C0 -30.6 3 -30 3.6 -27 C4.4 -20 5.4 -10 6.9 -1.2 L-7.8 -1.2 C-6.5 -6 -5.1 -14 -4.7 -20 C-4.5 -24 -4.1 -27.6 -3 -29.6 Z",
  // shayla over the head and shoulders
  "M3.1 -35.6 C2.3 -38.7 -2.7 -38.7 -3.3 -35 C-3.7 -31.6 -3.8 -29.4 -3.4 -27.4 L1.8 -28.6 C2.3 -30 2.5 -31.4 2.5 -32.4 C2.5 -33.6 2.7 -34.6 3.1 -35.6 Z",
  // face
  "M1.5 -35.2 C2.6 -35.3 3.3 -34.3 3.2 -33 C3.2 -32.1 2.8 -31.5 2.2 -31.3 L1.3 -31.5 Z",
  // arm and handbag
  "M0.8 -27.8 C2.4 -24 3.2 -20.4 3.5 -17.4 L2.3 -17.2 C1.9 -20 0.9 -23.4 -0.6 -26.6 Z",
  "M1.6 -18.2 L5.2 -18.2 L5.6 -14.2 L1.2 -14.2 Z",
  "M3.9 -1.5 L7.2 -0.5 L7.2 0 L3.6 0 Z",
];

const IGAL = { x: -2.9, y: -37.9, width: 6, height: 1.2 };

type Part = string[];

function Figure({ x, parts, scale = 1.3, flip = false, igal = true }: { x: number; parts: Part; scale?: number; flip?: boolean; igal?: boolean }) {
  return (
    <g transform={`translate(${x} 214) scale(${flip ? -scale : scale} ${scale})`}>
      {/* Rim pass first, then the dark fill, so only the outer edge glows. */}
      <g className="figure-rim">{parts.map((d) => <path key={d} d={d} />)}</g>
      <g className="figure-fill">{parts.map((d) => <path key={d} d={d} />)}</g>
      {igal && <rect className="igal" rx=".6" {...IGAL} />}
    </g>
  );
}

function Palm({ x, h = 46 }: { x: number; h?: number }) {
  return (
    <g transform={`translate(${x} 214)`}>
      <path d={`M-1.4 0 Q2 ${-h / 2} 1 ${-h} L2.6 ${-h} Q3.6 ${-h / 2} 1.4 0 Z`} />
      <g transform={`translate(1.8 ${-h})`}>
        <path d="M0 0 Q-10 -6 -18 2 Q-9 -2 0 1 Z" />
        <path d="M0 0 Q10 -6 18 2 Q9 -2 0 1 Z" />
        <path d="M0 0 Q-6 -10 -12 -12 Q-5 -6 0 0 Z" />
        <path d="M0 0 Q6 -10 13 -11 Q5 -6 0 0 Z" />
        <path d="M0 0 Q-1 -9 2 -14 Q1 -6 0 0 Z" />
      </g>
    </g>
  );
}

const WINDOWS: Array<[number, number]> = [
  [1032, 104], [1040, 122], [1036, 142], [1046, 160], [1180, 88], [1188, 110], [1176, 130], [1192, 152],
  [1310, 120], [1318, 140], [1306, 160], [1452, 132], [1460, 150], [368, 150], [376, 168], [214, 140],
  [222, 160], [1100, 140], [1108, 160], [1252, 98], [1258, 126],
];

export function Skyline({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 1600 230" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <defs>
        <linearGradient id="sky-haze" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e8be78" stopOpacity="0" />
          <stop offset=".78" stopColor="#e8be78" stopOpacity=".11" />
          <stop offset="1" stopColor="#e8be78" stopOpacity=".05" />
        </linearGradient>
        <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e8be78" stopOpacity=".1" />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="0" y="40" width="1600" height="160" fill="url(#sky-haze)" />

      {/* Far towers */}
      <g fill="#17171a">
        <rect x="150" y="128" width="34" height="72" />
        <rect x="200" y="118" width="40" height="82" rx="3" />
        <rect x="340" y="130" width="22" height="70" />
        <rect x="360" y="138" width="34" height="62" />
        <rect x="980" y="120" width="30" height="80" />
        <path d="M1020 200 L1022 90 Q1036 80 1050 90 L1054 200 Z" />
        <path d="M1090 200 L1092 124 L1118 112 L1120 200 Z" />
        <path d="M1166 200 Q1164 120 1174 76 Q1186 62 1198 76 Q1206 120 1204 200 Z" />
        <path d="M1240 200 Q1240 120 1250 84 Q1260 74 1268 84 Q1276 120 1274 200 Z" />
        <rect x="1296" y="110" width="34" height="90" rx="2" />
        <circle cx="1392" cy="150" r="34" />
        <rect x="1386" y="178" width="12" height="22" />
        <rect x="1440" y="120" width="30" height="80" />
        <rect x="1480" y="140" width="40" height="60" />
      </g>
      <g fill="#e8be78" opacity=".55">
        {WINDOWS.map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="2" height="2" />)}
      </g>

      {/* Grand mosque silhouette */}
      <g fill="#131316">
        <rect x="520" y="168" width="300" height="32" />
        <path d="M600 168 Q600 128 640 120 Q680 128 680 168 Z" />
        <path d="M638 120 L640 108 L642 120 Z" />
        <path d="M690 168 Q690 146 712 142 Q734 146 734 168 Z" />
        <path d="M546 168 Q546 150 564 146 Q582 150 582 168 Z" />
        <path d="M748 168 Q748 152 764 149 Q780 152 780 168 Z" />
        {[528, 596, 744, 812].map((x) => (
          <g key={x}>
            <rect x={x - 3} y="112" width="6" height="88" />
            <rect x={x - 4.5} y="134" width="9" height="3" />
            <path d={`M${x - 3} 112 Q${x} 104 ${x + 3} 112 Z`} />
            <path d={`M${x - 0.6} 104 L${x} 98 L${x + 0.6} 104 Z`} />
          </g>
        ))}
        {[560, 600, 640, 680, 720, 760].map((x) => (
          <path key={x} d={`M${x} 200 L${x} 186 Q${x + 9} 176 ${x + 18} 186 L${x + 18} 200 Z`} fill="#1a1a1d" />
        ))}
      </g>

      {/* Water and dhow */}
      <rect x="0" y="200" width="1600" height="14" fill="url(#water)" />
      <g className="dhow" fill="#0d0d0f">
        <path d="M880 199 Q905 206 936 199 L942 194 L874 194 Z" />
        <path d="M904 194 L906 150 L908 194 Z" />
        <path d="M907 152 Q932 170 936 192 L907 192 Z" />
        <path d="M904 160 Q888 176 884 191 L904 191 Z" />
      </g>

      {/* Corniche promenade */}
      <rect x="0" y="213" width="1600" height="17" fill="#08080a" />
      <rect x="0" y="213" width="1600" height="1" fill="#e8be78" opacity=".18" />
      <g fill="#08080a">
        <Palm x={90} h={44} />
        <Palm x={300} h={52} />
        <Palm x={470} h={40} />
        <Palm x={960} h={48} />
        <Palm x={1140} h={42} />
        <Palm x={1550} h={50} />
      </g>
      <g className="figures">
        <Figure x={226} parts={MAN_WALKING} />
        <Figure x={244} parts={MAN_WALKING} scale={0.82} />
        <Figure x={268} parts={WOMAN_WALKING} igal={false} />
        <Figure x={420} parts={[...MAN_STANDING, ...FALCON_ARM]} />
        <Figure x={998} parts={WOMAN_WALKING} igal={false} />
        <Figure x={1024} parts={MAN_STANDING} flip />
        <Figure x={1236} parts={MAN_WALKING} flip />
        <Figure x={1488} parts={WOMAN_WALKING} igal={false} flip />
        <Figure x={1508} parts={MAN_WALKING} scale={0.8} flip />
      </g>
    </svg>
  );
}
