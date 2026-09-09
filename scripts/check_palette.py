"""
check_palette.py — perceptual separation check for the food-group map palette.

The house rule is that a new categorical palette must be checked for OKLab distance before
shipping. This app adds two colours to the ten-group bright-on-dark set (Sugar and
Sweeteners, Stimulants and Spices), so all twelve are checked here as one palette.

Also checks each colour against the map ground (#080c16): a swatch that sits too close to
the basemap disappears at the 1-4 px widths these marks are drawn at.

Run: python3 scripts/check_palette.py
"""

import itertools
import math

PALETTE = {
    "Grains": "#f5c542", "Fruits": "#6ef5a0", "Vegetables": "#3dcc3d",
    "Meat and Fish": "#ff6b6b", "Dairy and Eggs": "#fff06a", "Oils and Oilseed": "#e89840",
    "Pulses": "#8c4c31", "Starchy Roots": "#d49ce8", "Treenuts": "#5ea54a",
    "Sugar and Sweeteners": "#4fd8e8", "Stimulants and Spices": "#6aa8ff", "Other": "#aaaaaa",
}
NEW = {"Sugar and Sweeteners", "Stimulants and Spices"}
MOVED = {"Fruits", "Pulses"}  # re-separated from the house set; see src/config/palette.ts
GROUND = "#080c16"

# Pairs below this OKLab distance read as the same colour at map line widths.
MIN_DISTANCE = 0.10
MIN_FROM_GROUND = 0.35


def srgb_to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(hex_str):
    h = hex_str.lstrip("#")
    r, g, b = (srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def dist(a, b):
    return math.dist(oklab(a), oklab(b))


def main():
    pairs = sorted(
        ((dist(PALETTE[x], PALETTE[y]), x, y) for x, y in itertools.combinations(PALETTE, 2))
    )
    failures = [p for p in pairs if p[0] < MIN_DISTANCE]

    print(f"{len(PALETTE)} colours, {len(pairs)} pairs, min distance {MIN_DISTANCE}\n")
    print("closest pairs:")
    for d, x, y in pairs[:6]:
        mark = "FAIL" if d < MIN_DISTANCE else "ok  "
        flag = " *" if {x, y} & (NEW | MOVED) else ""
        print(f"  {mark} {d:.3f}  {x} / {y}{flag}")

    print("\nchanged colours vs every other one (closest):")
    for n in sorted(NEW | MOVED):
        closest = min(((dist(PALETTE[n], v), k) for k, v in PALETTE.items() if k != n))
        print(f"  {closest[0]:.3f}  {n} -> nearest is {closest[1]}")

    print(f"\nvs map ground {GROUND} (min {MIN_FROM_GROUND}):")
    dim = [(dist(v, GROUND), k) for k, v in PALETTE.items() if dist(v, GROUND) < MIN_FROM_GROUND]
    for d, k in sorted(dim):
        print(f"  FAIL {d:.3f}  {k}")
    print("  all clear" if not dim else "")

    ok = not failures and not dim
    print("\n" + ("PASS — palette ships" if ok else "REVIEW NEEDED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
