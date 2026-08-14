import type { HTMLAttributes } from "react";

/**
 * Generic card primitive — every clinical panel in the app should compose this rather
 * than redefining border/shadow/radius inline. Backed by the `.gms-card` utility class
 * (src/styles/index.css) so the visual language stays defined in exactly one place.
 */
export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`gms-card ${className}`} {...props} />;
}
