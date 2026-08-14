/**
 * Original inline SVG artwork (no external image dependency) echoing the composition
 * of the reference dashboard screenshot (docs/ui-reference/) — a clinical document,
 * an AI assist bubble, and a privacy/trust mark — built from GMS palette tokens.
 *
 * This can be swapped for an AI-generated raster illustration later: drop a PNG at
 * `frontend/public/images/hero-illustration.png` and replace this component's usage
 * in Overview/index.tsx with an <img>. Suggested generation prompt:
 *   "Minimal isometric-style illustration of a clinical document with a chat/assist
 *    bubble and a shield/lock trust icon, soft blue and cyan palette (#246BFD,
 *    #15B7E8, #EDF5FF, #102347), flat vector style, white background, no text,
 *    professional medical-software aesthetic, plenty of negative space."
 */
export function HeroIllustration() {
  return (
    <svg viewBox="0 0 420 360" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-hidden="true">
      <circle cx="210" cy="180" r="170" fill="#EDF5FF" />

      {/* Document card */}
      <rect x="110" y="70" width="180" height="220" rx="16" fill="#FFFFFF" stroke="#E3EAF4" strokeWidth="2" />
      <rect x="132" y="100" width="90" height="10" rx="5" fill="#102347" />
      <rect x="132" y="122" width="136" height="6" rx="3" fill="#E3EAF4" />
      <rect x="132" y="138" width="136" height="6" rx="3" fill="#E3EAF4" />
      <rect x="132" y="154" width="96" height="6" rx="3" fill="#E3EAF4" />

      {/* Mini trend chart inside the document */}
      <polyline
        points="132,230 156,214 180,222 204,196 228,204 252,182"
        fill="none"
        stroke="#246BFD"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="252" cy="182" r="4" fill="#246BFD" />
      <rect x="132" y="252" width="60" height="18" rx="9" fill="#EDF5FF" />
      <rect x="140" y="258" width="44" height="6" rx="3" fill="#15B7E8" />

      {/* Assist bubble */}
      <rect x="252" y="56" width="112" height="72" rx="16" fill="#246BFD" />
      <path d="M270 128 L270 148 L292 128 Z" fill="#246BFD" />
      <circle cx="280" cy="92" r="5" fill="#FFFFFF" />
      <circle cx="308" cy="92" r="5" fill="#FFFFFF" />
      <circle cx="336" cy="92" r="5" fill="#FFFFFF" />

      {/* Trust / privacy badge */}
      <circle cx="120" cy="270" r="34" fill="#FFFFFF" stroke="#E3EAF4" strokeWidth="2" />
      <path
        d="M120 252c8 0 14 3 14 3v14c0 10-6 17-14 21-8-4-14-11-14-21v-14s6-3 14-3Z"
        fill="#14B86E"
      />
      <path d="M113 270l5 5 10-11" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
