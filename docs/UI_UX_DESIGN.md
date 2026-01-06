# Tiger-Cafe Design System

**Visual Goal**: Premium minimalism (Apple/Tesla inspired). Refined spacing, restrained color, soft depth.

## Core Rules
1. **Font**: `Inter` (sans-serif). Heading: Semi-bold, tight tracking. Body: Regular, 1.5 line-height.
2. **Radius**: 8px (small), 12px (medium/default), 18px (large).
3. **Shadows**: Soft, diffused, layered. No harsh black shadows.
4. **Borders**: Subtle 1px borders.

## Colors & Themes
**Support both Day & Night modes.**

| Element | Day Mode | Night Mode |
| :--- | :--- | :--- |
| **Bg Primary** | `#F5F6F8` | `#0D0F12` |
| **Bg Surface** | `#FFFFFF` | `#1B1E24` |
| **Text Main** | `#101113` | `#E0E0E0` |
| **Text Muted** | `#5B616E` | `#9CA3AF` |
| **Accent** | `#0A84FF` (Blue) | `#0A84FF` |
| **Border** | `#E5E7EB` | `#2D3748` |

## Components
- **Buttons**: Pill-shaped or Rounded-md (8-12px).
  - *Primary*: Solid Accent color.
  - *Secondary*: Outline or Surface color with subtle border.
- **Inputs**: Soft border, focus ring `3px` with `15%` alpha accent.
- **Cards**: Surface color, 12px radius, subtle border + shadow-sm.
- **Modals**: Large radius (18-24px), shadow-xl, backdrop blur.
- **Table Rows**: Clean, spacious (48px+ height), minimal dividers.

## Spacing
- **Base Unit**: 4px.
- **Padding**: Panels (24-32px), Cards (16-24px), Items (12px).
- **Gap**: Consistently use `gap-2` (8px), `gap-4` (16px), `gap-6` (24px).

## Table Design Specs
- **Metadata Header**: Display *Time Period*, *Currency*, and *Units* clearly above the grid (muted style).
- **Column Structure**:
  1. **Line Item**: Left-aligned. Primary text weight.
  2. **Category**: Left-aligned. Muted/Secondary text color.
  3. **Type**: Right-aligned. Use **Status Pills** (e.g. Green for `Operating`, Red/Amber for `Non-Operating`).

## Workflow Reference
For functional specs and user flows, see `docs/PRODUCT_SPECS.md`.