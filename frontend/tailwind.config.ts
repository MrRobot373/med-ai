import type { Config } from "tailwindcss";

// GMS visual language — palette locked from the Master Build Prompt §20 and the
// supplied reference screenshots (see docs/ui-reference/). Every color used in the UI
// should come from this token set rather than raw Tailwind defaults or ad-hoc hexes.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#F8FBFF",
        surface: "#FFFFFF",
        navy: "#102347",
        "primary-blue": "#246BFD",
        cyan: "#15B7E8",
        "light-blue": "#EDF5FF",
        border: "#E3EAF4",
        success: "#14B86E",
        danger: "#E84040",
        "gms-red": "#140203",
        "muted-text": "#66758C",
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(16, 35, 71, 0.06), 0 1px 6px 0 rgba(16, 35, 71, 0.04)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
