# Icon / resource resolution

How this add-in finds Fusion's built-in icons (timeline glyphs, the right-click
menu icons, feature browser icons). Read this before touching icon paths — the
layout is non-obvious and differs between macOS and Windows.

## The deploy folder

All built-in icons live under Fusion's *deploy folder*, resolved at runtime by
`thomasa88lib.utils.get_fusion_deploy_folder()`. That function takes the Fusion
Solid environment's `resourceFolder` and strips the trailing
`/Fusion/UI/FusionUI/Resources`, so the base it returns is **not the same shape
on both platforms**:

| Platform | Deploy-folder base (roughly) |
|----------|------------------------------|
| Windows  | `…/AppData/Local/Autodesk/webdeploy/production/<hash>` |
| macOS    | `…/Autodesk Fusion.app/Contents/Libraries/Applications/Fusion` |

`get_image_path('<subpath>')` joins the base + subpath and then probes for an
icon file (see "Filenames" below). Because the base is computed per-platform,
**subpaths that start with `Fusion/UI/FusionUI/Resources/…` work on both
platforms** even though the absolute paths look nothing alike. Examples that
already rely on this: `Timeline/RollFwd`, `Timeline/GroupFeature`,
`modify/delete` (the Delete red X).

## Two resource trees: Fusion vs Neutron

Built-in icons come from two different libraries:

- **Fusion** tree — `Fusion/UI/FusionUI/Resources/…`. Reachable directly from the
  deploy-folder base on both platforms (see above).
- **Neutron** tree — a *separate* library that does **not** sit under the deploy
  base, and whose location relative to that base is different per platform:

  | Platform | Neutron subpath to pass to `get_image_path` |
  |----------|---------------------------------------------|
  | Windows  | `Neutron/UI/…` |
  | macOS    | `../../Neutron/Neutron/UI/…` (note: doubled `Neutron`, and `../../` to climb out of `Applications/Fusion`) |

Because of this split, Neutron icons are looked up with a **candidate list** that
includes both layouts, and the first one that exists wins. See
`SKETCH_FULLY_CONSTRAINED_RES` in `VerticalTimeline.py` and the
`get_first_image_path()` helper.

## Filenames (theme-split icons)

A single icon folder usually contains several files, e.g.:

```
16x16.png  16x16-dark.png  16x16-dark.svg  16x16.svg  16x16@2x.png  …themed svgs…
```

The palette draws icons in a 16px box, but on Retina a 16px source looks soft —
it needs a 32px source downscaled into that box. So `get_image_path()` prefers
the 2x rasters (`16x16@2x.png`, `32x32.png`) over the 1x `16x16.png`, with SVG
last.

Icons are also **theme-split**. The neutral files (`16x16.png`, …) have a *dark*
foreground — correct on a light background; some glyph detail (e.g. the extrude
arrow) is only present at 2x and would be invisible on a dark background. The
`-dark` files (`16x16-dark@2x.png`, …) have a *light* foreground — correct on a
dark background. Fusion swaps these by theme and so do we.

The palette is theme-adaptive (`prefers-color-scheme`, see the light/dark CSS
vars in `palette.html`), and Python can't know which theme is rendered. So
`get_image_path(subpath, dark=...)` resolves **both** variants (the `dark=True`
set falls back to the neutral set for icons that ship no `-dark` file), the
add-in sends both to the palette, and the palette picks via
`matchMedia('(prefers-color-scheme: dark)')`:

- Row icons: each feature carries `image` (light) and `imageDark`; see
  `set_feature_image()` and `get_feature_image()`.
- Menu icons: `get_menu_icons()` returns `{light, dark}` pairs; the palette's
  `pickIcon()` chooses.

Theme changes apply on the next timeline refresh (icons are not re-swapped live).

> Gotcha that this caused: the right-click **Delete** entry used to borrow the
> live `DeleteCommand`'s `resourceFolder` and only checked `{folder}/16x16.png`.
> When that lookup stopped resolving, the entry showed no icon. It now points at
> the stable subpath `Fusion/UI/FusionUI/Resources/modify/delete`, which ships a
> plain `16x16.png` (the red X) and resolves on both platforms.

## Helpers (in `VerticalTimeline.py`)

- `get_image_path(subpath, dark=False)` — base + subpath, probes the filename
  variants above (the `-dark` set when `dark=True`), cached per (subpath, dark).
  Returns `None` (and logs) if nothing matches.
- `get_first_image_path([sub, sub, …], dark=False)` — first candidate subpath
  that resolves; use this for icons whose layout differs per platform (Neutron).
- `set_feature_image(feature, subpath_or_list)` — sets both `feature['image']`
  (light) and `feature['imageDark']`.
- `FEATURE_RESOURCE_MAP` — maps a feature's short class to a resource subpath (or
  a list of candidate subpaths) for the browser-row icon.
- `get_menu_icons()` — resolves the right-click menu icons once, cached.
