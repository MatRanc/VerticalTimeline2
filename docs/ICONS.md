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

Most icons still ship a plain `16x16.png`, but some newer ones are dark/SVG only.
`get_image_path()` therefore tries, in order: `16x16.png`, `16x16-dark.svg`,
`16x16.svg`. The palette renders dark, so a dark/neutral variant is fine.

> Gotcha that this caused: the right-click **Delete** entry used to borrow the
> live `DeleteCommand`'s `resourceFolder` and only checked `{folder}/16x16.png`.
> When that lookup stopped resolving, the entry showed no icon. It now points at
> the stable subpath `Fusion/UI/FusionUI/Resources/modify/delete`, which ships a
> plain `16x16.png` (the red X) and resolves on both platforms.

## Helpers (in `VerticalTimeline.py`)

- `get_image_path(subpath)` — base + subpath, probes the filename variants above,
  cached. Returns `None` (and logs) if nothing matches.
- `get_first_image_path([sub, sub, …])` — first candidate subpath that resolves;
  use this for icons whose layout differs per platform (i.e. Neutron icons).
- `FEATURE_RESOURCE_MAP` — maps a feature's short class to a resource subpath (or
  a list of candidate subpaths) for the browser-row icon.
- `get_menu_icons()` — resolves the right-click menu icons once, cached.
