import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useBranding, useMe, useSavePreferences } from "@/api/hooks";
import type { Preferences } from "@/api/types";
import { accentVars } from "@/lib/color";

export type Appearance = Required<Pick<Preferences, "theme" | "density" | "radius" | "font_scale" | "font_family" | "contrast" | "reduce_motion" | "sidebar_collapsed">> & { accent: string | null };

const DEFAULTS: Appearance = {
  theme: "light", accent: null, density: "comfortable", radius: "default", font_scale: "md",
  font_family: "inter", contrast: "normal", reduce_motion: false, sidebar_collapsed: false,
};
const STORAGE_KEY = "gms.appearance";

interface Ctx {
  appearance: Appearance;
  resolvedTheme: "light" | "dark";
  effectiveAccent: string;
  update: (patch: Partial<Appearance>) => void;
  reset: () => void;
}

const AppearanceContext = createContext<Ctx | null>(null);

function readLocal(): Partial<Appearance> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function useSystemDark() {
  const [dark, setDark] = useState(() => typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const fn = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return dark;
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const { data: branding } = useBranding();
  const { data: me } = useMe();
  const save = useSavePreferences();
  const [local, setLocal] = useState<Partial<Appearance>>(readLocal);
  const systemDark = useSystemDark();
  const syncedFor = useRef<string | null>(null);
  const saveTimer = useRef<number>();

  // When a user signs in, their saved preferences win over this browser's.
  useEffect(() => {
    if (me && syncedFor.current !== me.id) {
      syncedFor.current = me.id;
      const prefs = me.preferences ?? {};
      if (Object.keys(prefs).length) setLocal((cur) => ({ ...cur, ...(prefs as Partial<Appearance>) }));
    }
  }, [me]);

  const appearance: Appearance = useMemo(
    () => ({ ...DEFAULTS, theme: branding?.default_theme ?? DEFAULTS.theme, ...local }),
    [branding?.default_theme, local],
  );
  const resolvedTheme = appearance.theme === "system" ? (systemDark ? "dark" : "light") : appearance.theme;
  const effectiveAccent = appearance.accent || branding?.default_accent || "#246BFD";

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolvedTheme === "dark");
    root.dataset.density = appearance.density;
    root.dataset.contrast = appearance.contrast;
    root.dataset.reduceMotion = String(appearance.reduce_motion);
    root.style.setProperty("--radius", { sharp: "0.4rem", default: "0.875rem", round: "1.2rem" }[appearance.radius]);
    root.style.setProperty("--root-size", { sm: "14px", md: "15px", lg: "16.5px" }[appearance.font_scale]);
    root.style.setProperty("--font-sans", appearance.font_family === "system" ? "system-ui, -apple-system, 'Segoe UI'" : "'Inter Variable', Inter");
    for (const [k, v] of Object.entries(accentVars(effectiveAccent, resolvedTheme === "dark"))) root.style.setProperty(k, v);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", effectiveAccent);
  }, [appearance, resolvedTheme, effectiveAccent]);

  useEffect(() => {
    if (branding?.product_name) document.title = branding.product_name;
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (icon && branding?.logo_data_url) icon.href = branding.logo_data_url;
  }, [branding?.product_name, branding?.logo_data_url]);

  const update = useCallback(
    (patch: Partial<Appearance>) => {
      setLocal((cur) => {
        const next = { ...cur, ...patch };
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch {
          /* storage unavailable */
        }
        return next;
      });
      if (me) {
        window.clearTimeout(saveTimer.current);
        saveTimer.current = window.setTimeout(() => save.mutate(patch), 400);
      }
    },
    [me, save],
  );

  const reset = useCallback(() => {
    setLocal({});
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    if (me) save.mutate({ ...DEFAULTS, theme: branding?.default_theme ?? "light", accent: null });
  }, [me, save, branding?.default_theme]);

  return <AppearanceContext.Provider value={{ appearance, resolvedTheme, effectiveAccent, update, reset }}>{children}</AppearanceContext.Provider>;
}

export function useAppearance() {
  const ctx = useContext(AppearanceContext);
  if (!ctx) throw new Error("useAppearance outside provider");
  return ctx;
}
