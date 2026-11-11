# Product and Documentation Design System

This project-level system adapts the restrained enterprise layout rules in the installed
[`oracle/DESIGN.md`](oracle/DESIGN.md) reference installed from
[getdesign.md/oracle/design-md](https://getdesign.md/oracle/design-md). It keeps the warm neutral surface ladder, compact actions,
strong information hierarchy, and disciplined spacing while replacing Oracle brand cues with
the YouBike palette and the product's transit-data semantics.

## Direction

The product and documentation share one visual language: clear public-transit information,
high-contrast operational data, and restrained YouBike-inspired colour. The interface should
feel professional enough for an engineering review and simple enough for a rider to understand.

## Colour tokens

| Token | Value | Use |
|---|---|---|
| YouBike orange | `#F28C00` | Primary actions, active navigation, data emphasis |
| Signal yellow | `#FFD83D` | Forecast highlights, progress, selected states |
| Warm white | `#FFFDF7` | Primary page background |
| Soft cream | `#FFF4D6` | Secondary surfaces and status panels |
| Charcoal | `#27231C` | Primary text and high-contrast overlays |
| Muted brown-grey | `#71695D` | Supporting text |
| Border | `rgba(83, 66, 38, 0.18)` | Dividers and card outlines |

Orange communicates action; yellow communicates forecast or attention. Neither colour should be
used as body text on white without a darker companion. Operational risk colours on the station
map remain red, amber, green, and blue because they encode meaning rather than brand.

## Typography

- Headings: Manrope, bold, compact tracking.
- Body: Manrope for the product; Inter and Noto Sans TC for documentation readability.
- Data and status labels: DM Mono or IBM Plex Mono.
- Large headings use short lines and one clear conclusion.

## Layout and components

- White or cream backgrounds are primary; charcoal is reserved for maps, overlays, and dense
  operational panels.
- Cards use one-pixel borders, minimal radius, and no decorative shadows unless they clarify
  layering.
- Primary buttons are orange with charcoal text; forecast emphasis uses yellow.
- Navigation always exposes both `Product` and `Documentation` destinations.
- Desktop documentation uses a persistent categorized left sidebar; mobile uses a drawer.
- English and Traditional Chinese must contain the same document set and route structure.
- Search is local, keyboard accessible, and language-aware.
- Layouts are designed mobile-first at 320 px, then verified at phone, tablet, laptop, and wide
  desktop widths. Navigation, map overlays, metrics, tables, and side panels must never create
  horizontal page overflow.

## Accessibility

- Maintain visible focus styles and WCAG AA text contrast.
- Do not rely on orange or yellow alone to communicate risk.
- All icon-only controls require accessible labels.
- Tables scroll horizontally on narrow screens; page layouts must not create body overflow.
