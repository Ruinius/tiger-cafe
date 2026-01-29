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
3. **Click Behavior (Immediate Feedback / Debouncing)**: Upon click, the button must **immediately** transition to a `disabled` (loading) state. Do not wait for API response.
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

## Mission Control & Intelligence Stream
The "Mission Control" panel provides a high-fidelity, real-time command center for document processing.

- **The Intelligence Stream**:
  - **Message Bubbles**: Rounded-md bubbles with a `2px` bottom-right radius for a distinct "log" feel.
  - **AI Insights (Gemini & Tiger Transformer)**:
    - **Background**: `linear-gradient(135deg, #6366f1 0%, #a855f7 100%)`.
    - **Text**: White.
    - **Shadow**: `0 4px 12px rgba(168, 85, 247, 0.2)`.
  - **System Logs**:
    - **Background**: Transparent with subtle border or light grey surface.
    - **Text**: `var(--text-main)`.
- **Source Tags**:
  - Small, uppercase badges indicating the origin:
    - `SYSTEM`: Neutral grey / text-secondary.
    - `GEMINI`: Indigo / Purple.
    - `TIGER TRANSFORMER`: Indigo / Purple (Unified with Gemini for visual harmony).
- **Animations**:
  - New logs should "drip" in with a subtle fade-and-slide up animation.
  - Active steps should feature a soft Pulse animation on the status icon.

## Table Design ("The Gold Standard")
*Reference Implementation: Document View (DocumentExtractionView)*


- **Container Card**:
  - **Background**: Surface color (`#FFFFFF` / `#1B1E24`).
  - **Border**: `1px solid var(--border)`.
  - **Radius**: `12px` (Medium).
  - **Shadow**: Soft, layered (`0 1px 3px rgba(0,0,0,0.05)`).
  - **Overflow**: Hidden (clips child content).

- **Header (Thead)**:
  - **Background**: `var(--bg-primary)` (Subtle contrast to surface).
  - **Border**: Bottom `1px solid var(--border)`.
  - **Text**: Uppercase, `0.75rem`, weight `600`, tracking `0.05em`.
  - **Color**: `var(--text-secondary)` (Muted).
  - **Padding**: `1rem 1.5rem` (Generous horizontal padding).

- **Rows (Tr)**:
  - **Height**: Fixed `48px` minimum for touch targets and breathability.
  - **Border**: Bottom `1px solid var(--border-subtle)` (Very faint).
  - **Hover**: Transitions to `var(--bg-primary)`.
  - **"Key Total" Rows**:
    - **Backround**: `var(--bg-primary)`.
    - **Borders**: Top and Bottom `1px solid var(--border)`.
    - **Font**: Weight `600` (Semi-bold).

- **Cells (Td)**:
  - **Padding**: `0.75rem 1.5rem`.
  - **Alignment**:
    - **Text**: Left.
    - **Numbers**: Right (`font-variant-numeric: tabular-nums`).
  - **Type/Status**: Right-aligned pills.

- **Badges & Pills**:
  - **Shape**: Full pill (`border-radius: 9999px`).
  - **Typography**: `0.75rem`, weight `600`, tracking `0.025em`.
  - **Operating**: Green (Emerald) background (10% opacity) + Text.
  - **Non-Operating**: Amber background (10% opacity) + Text.
  - **Qualitative (Moat/Growth)**: 
    - *Good/Wide/Faster*: Green (Success).
    - *Neutral/Narrow/Steady*: Grey (Neutral).
    - *Bad/None/Slower*: Orange (Warning).
  - **Void/Null**: Simple muted dash "—".

## Spacing & Layout Structure
- **Global Panel Padding**: `2rem` (vertical) `2.5rem` (horizontal).
- **Section Spacing**: `gap: 2.5rem` between major extractions.
- **Header Spacing**: Bottom margin `2rem` for main titles.
- **Metadata**: Displayed in a flex row above tables, `0.875rem`, `text-secondary`.

## Workflow Reference
For functional specs and user flows, see `docs/PRODUCT_SPECS.md`.