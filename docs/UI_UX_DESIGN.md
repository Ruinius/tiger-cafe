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
| **Accent** | `#0A84FF` (Blue) | `#5AA5FF` |
| **Border** | `#E5E7EB` | `#2B313A` |
| **Border Subtle**| `#F3F4F6` | `#262A33` |

## Interactive Elements & Button Logic
**Strict Rules for Button States & Behavior:**
1. **Initial State**: Buttons must load quickly. If dependencies are not met (e.g., file not selected), they start `disabled`.
2. **Enable Condition**: Buttons become `enabled` *only* after specific conditions are fully met.
3. **Click Behavior (Immediate Feedback)**: Upon click, the button must **immediately** transition to a `disabled` (loading) state. Do not wait for API response.
4. **Cross-Component Signaling**: Clicking a primary action button should immediately signal other dependent buttons to disable via state push, preventing race conditions or double-submissions.
5. **Re-enable Logic**: Buttons should re-enable via explicit "push" events (e.g., "Process Complete") rather than relying solely on passive background polling.

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
- **Container**: Surface color, 12px radius, shadow-sm, 1px border.
- **Rows**: Spacious (`48px` height), `border-bottom` using `var(--border-subtle)` (no high contrast lines).
- **Metadata Header**: Display *Time Period*, *Currency*, and *Units* clearly above the grid (muted style).
- **Column Structure**:
  1. **Line Item**: Left-aligned. Weight 500 (Medium).
  2. **Category**: Left-aligned. Muted/Secondary text color.
  3. **Amount**: **Right-aligned**. Weight 500. Tabular nums.
  4. **Type**: **Right-aligned**. Use **Status Pills** (Pill shape, capitalized, distinct colors for Operating/Non-Op).

## Workflow Reference
For functional specs and user flows, see `docs/PRODUCT_SPECS.md`.