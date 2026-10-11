// Solid aircraft glyph adapted from Material Symbols "flight" (Apache-2.0).
export const PLANE_PATH =
  "M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z";

export function LogoMark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="AeroStay">
      <rect width="32" height="32" rx="8" fill="#000" />
      <rect x=".5" y=".5" width="31" height="31" rx="7.5" fill="none" stroke="rgba(255,255,255,.14)" />
      <g transform="translate(16 16) rotate(45) scale(.86) translate(-11.5 -12)">
        <path d={PLANE_PATH} fill="#fff" />
      </g>
    </svg>
  );
}

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="logo-word">AeroStay</span>
    </span>
  );
}
