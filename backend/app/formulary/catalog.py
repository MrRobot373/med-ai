"""Loads a region's formulary and resolves what a doctor writes ("Dolo 650",
"Tab. Pan-D", "Augmentin 625", "pantoprazole 40 mg") into generic components with
amounts per unit."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

FORM_PREFIXES = {
    "tab": "tab",
    "tabs": "tab",
    "tablet": "tab",
    "tablets": "tab",
    "cap": "cap",
    "caps": "cap",
    "capsule": "cap",
    "capsules": "cap",
    "syp": "syrup",
    "syr": "syrup",
    "syrup": "syrup",
    "susp": "syrup",
    "suspension": "syrup",
    "liquid": "syrup",
    "sachet": "sachet",
    "inj": "inj",
    "injection": "inj",
}
LIQUID_FORMS = {"syrup"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fmt_amount(value: float) -> str:
    return f"{value:g}" if value < 1000 else f"{value:,.0f}"


@dataclass
class Generic:
    id: str
    name: str
    unit: str
    data: dict

    @property
    def tags(self) -> list[str]:
        return self.data.get("tags", [])

    @property
    def drug_class(self) -> str:
        return self.data.get("class", "")


@dataclass
class Product:
    key: str
    label: str  # "Dolo 650"
    brand: str | None
    form: str
    components: dict[str, float]  # generic id -> amount per tab/cap (or per mL for liquids)
    per_ml: bool = False
    strength: float | None = None  # single-ingredient strength, as written on the pack
    strength_label: str | None = None


@dataclass
class Resolved:
    text: str
    product: Product | None
    generics: list[Generic] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)  # amount per unit; empty if strength unknown
    form: str = "tab"
    per_ml: bool = False
    strength_known: bool = False
    matched: bool = False

    @property
    def generic_ids(self) -> list[str]:
        return [g.id for g in self.generics]

    def describe(self) -> str:
        if not self.generics:
            return self.text
        parts = []
        for g in self.generics:
            amt = self.components.get(g.id)
            unit = g.unit + ("/mL" if self.per_ml else "")
            parts.append(f"{g.name} {fmt_amount(amt)} {unit}" if amt is not None else g.name)
        return " + ".join(parts)


class Formulary:
    def __init__(self, data: dict):
        self.meta = data.get("_meta", {})
        self.region = self.meta.get("region", "IN")
        self.generics: dict[str, Generic] = {
            g["id"]: Generic(g["id"], g["name"], g.get("unit", "mg"), g) for g in data["generics"]
        }
        self.allergy_groups: dict[str, list[str]] = data.get("allergy_groups", {})
        self.cross_reactivity: list[dict] = data.get("cross_reactivity", [])
        self.duplicate_classes: set[str] = set(data.get("duplicate_classes", []))
        self.interactions: list[dict] = data.get("interactions", [])
        self.synonyms: dict[str, str] = {norm(k): v for k, v in data.get("synonyms", {}).items()}
        self.products: list[Product] = []
        self._by_brand: dict[str, list[Product]] = {}
        for p in data.get("products", []):
            self._expand(p)
        self._generic_keys = {norm(g.name): g.id for g in self.generics.values()}
        self._generic_keys.update({norm(g.id): g.id for g in self.generics.values()})

    # -- loading ---------------------------------------------------------------------------
    def _add(self, product: Product) -> None:
        self.products.append(product)
        self._by_brand.setdefault(norm(product.brand or ""), []).append(product)

    def _expand(self, p: dict) -> None:
        brand, form = p["brand"], p.get("form", "tab")
        if "generic" in p:
            gid = p["generic"]
            for s in p.get("strengths", []):
                self._add(
                    Product(
                        f"{norm(brand)}:{form}:{s:g}",
                        f"{brand} {s:g}",
                        brand,
                        form,
                        {gid: float(s)},
                        strength=float(s),
                        strength_label=f"{s:g}",
                    )
                )
            for s in p.get("per_5ml", []):
                self._add(
                    Product(
                        f"{norm(brand)}:{form}:{s:g}",
                        f"{brand} {s:g}/5 mL",
                        brand,
                        form,
                        {gid: s / 5},
                        per_ml=True,
                        strength=float(s),
                        strength_label=f"{s:g}",
                    )
                )
        for combo_key, per_ml in (("combo", False), ("combo_per_5ml", True)):
            for label, comps in (p.get(combo_key) or {}).items():
                amounts = {g: (a / 5 if per_ml else float(a)) for g, a in comps.items()}
                name = f"{brand} {label}".strip()
                self._add(
                    Product(
                        f"{norm(brand)}:{form}:{label}",
                        name,
                        brand,
                        form,
                        amounts,
                        per_ml=per_ml,
                        strength_label=label or None,
                    )
                )

    # -- lookup ----------------------------------------------------------------------------
    def generic(self, gid: str | None) -> Generic | None:
        return self.generics.get(gid) if gid else None

    def find_generic(self, text: str) -> Generic | None:
        key = norm(text)
        gid = self._generic_keys.get(key) or self.synonyms.get(key)
        if gid and not gid.startswith("@"):
            return self.generics.get(gid)
        return None

    def resolve(self, text: str, strength: float | None = None, dose_unit: str | None = None) -> Resolved:
        raw = (text or "").strip()
        words = [w.strip(".,") for w in raw.lower().split()]
        form_hint = None
        while words and words[0] in FORM_PREFIXES:
            form_hint = FORM_PREFIXES[words.pop(0)]
        if dose_unit == "ml" and form_hint is None:
            form_hint = "syrup"
        body = " ".join(w for w in words if w)
        # Trailing strength: "650", "40 mg", "50/500", "60000 iu", "625mg"
        m = re.search(r"\s*(?<![a-z])(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s*(mg|mcg|µg|g|iu|ml)?\s*$", body)
        written_strength = None
        if m and m.start() > 0:
            written_strength = m.group(1)
            unit = m.group(2)
            name = body[: m.start()].strip(" -")
            if unit == "g" and "/" not in written_strength:
                written_strength = f"{float(written_strength) * 1000:g}"
        else:
            name = body
        if strength is not None and written_strength is None:
            written_strength = f"{strength:g}"

        key = norm(name)
        syn = self.synonyms.get(key)
        if syn and syn.startswith("@"):
            key = norm(syn[1:])
        candidates = self._by_brand.get(key, [])
        if candidates:
            return self._pick(raw, candidates, written_strength, form_hint)

        generic = self.find_generic(name) or self.find_generic(body)
        if generic is None:
            return Resolved(raw, None)
        amount = None
        if written_strength and "/" not in written_strength:
            amount = float(written_strength)
        per_ml = form_hint in LIQUID_FORMS
        return Resolved(
            raw,
            None,
            [generic],
            {generic.id: amount} if amount is not None and not per_ml else {},
            form_hint or "tab",
            per_ml=False,
            strength_known=amount is not None and not per_ml,
            matched=True,
        )

    def _pick(self, raw: str, candidates: list[Product], strength: str | None, form_hint: str | None) -> Resolved:
        pool = [
            c
            for c in candidates
            if form_hint is None or c.form == form_hint or (form_hint == "tab" and c.form == "cap")
        ] or candidates
        if form_hint is None:
            solid = [c for c in pool if not c.per_ml]
            pool = solid or pool
        chosen = None
        if strength:
            chosen = next((c for c in pool if c.strength_label == strength), None)
            if chosen is None:
                try:
                    val = float(strength.split("/")[0])
                    chosen = next((c for c in pool if c.strength == val), None)
                except ValueError:
                    pass
        if chosen is None and len({c.strength_label for c in pool}) == 1:
            chosen = pool[0]
        if chosen is None:
            # Brand recognised but not the strength: generics are known, amounts are not.
            gids = list(dict.fromkeys(g for c in pool for g in c.components))
            return Resolved(
                raw, None, [self.generics[g] for g in gids if g in self.generics], {}, pool[0].form, matched=True
            )
        gens = [self.generics[g] for g in chosen.components if g in self.generics]
        return Resolved(raw, chosen, gens, dict(chosen.components), chosen.form, chosen.per_ml, True, True)

    def search(self, query: str, limit: int = 12) -> list[dict]:
        q = norm(query)
        if not q:
            return []
        results: list[tuple[int, dict]] = []
        for p in self.products:
            bk = norm(p.label)
            gnames = " ".join(self.generics[g].name for g in p.components if g in self.generics)
            if bk.startswith(q):
                rank = 0
            elif norm(p.brand or "").startswith(q[: max(2, len(q) - 3)]) and q in bk:
                rank = 1
            elif q in norm(gnames):
                rank = 3
            else:
                continue
            results.append((rank, self.product_option(p)))
        for g in self.generics.values():
            if norm(g.name).startswith(q) or (len(q) >= 3 and q in norm(g.name)):
                results.append(
                    (
                        2,
                        {
                            "label": g.name,
                            "drug": g.name,
                            "generic": g.id,
                            "generic_label": g.name,
                            "strength": None,
                            "form": "tab",
                            "brand": None,
                            "class": g.drug_class,
                            "unit": g.unit,
                        },
                    )
                )
        results.sort(key=lambda r: (r[0], r[1]["label"]))
        seen, out = set(), []
        for _, r in results:
            if r["label"] in seen:
                continue
            seen.add(r["label"])
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def product_option(self, p: Product) -> dict:
        gens = [self.generics[g] for g in p.components if g in self.generics]
        comp = " + ".join(
            f"{g.name} {fmt_amount(p.components[g.id] * (5 if p.per_ml else 1))} {g.unit}{'/5 mL' if p.per_ml else ''}"
            for g in gens
        )
        return {
            "label": p.label,
            "drug": p.label,
            "generic": "+".join(g.id for g in gens),
            "generic_label": comp,
            "strength": p.strength if len(gens) == 1 else None,
            "form": p.form,
            "brand": p.brand,
            "class": gens[0].drug_class if len(gens) == 1 else "Combination",
            "unit": gens[0].unit if gens else "mg",
        }


@lru_cache(maxsize=4)
def load(region: str = "IN") -> Formulary:
    path = DATA_DIR / f"{region.lower()}.json"
    if not path.exists():
        raise ValueError(f"No formulary data for region {region}")
    return Formulary(json.loads(path.read_text(encoding="utf-8")))
