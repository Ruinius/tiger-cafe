# Tiger-Cafe UI/UX Design Guide

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

This document captures the UI/UX requirements for the Tiger-Cafe application, with emphasis on the shared dashboard workflow and document processing lifecycle.

## Design Principles

1. **Day/night mode** with a persistent toggle.
2. **Two-panel workspace** after login (adjustable split screens).
3. **Shared global dashboard**: every authenticated user sees the same workspace.
4. **Attribution-only authentication**: login is used to track who did what, not to isolate data.
5. **Premium minimalism**: refined spacing, restrained color, and quiet surfaces inspired by Apple/Tesla UI language.

## Styling Guide

### Visual Tone
- Clean, minimal, and premium with soft depth.
- Surfaces feel layered through subtle shadows and gentle borders.
- Typography is quiet and confident; avoid heavy decorative styles.

### Typography
- Primary font: **Inter** (with system fallback).
- Headings: semi-bold with slight negative letter spacing for a tight, modern feel.
- Body: regular weight with generous line-height (1.5).

### Color Palette
- Primary background: `#F5F6F8` (day), `#0D0F12` (night).
- Surface background: `#FFFFFF` (day), `#1B1E24` (night).
- Accent color: Apple-style blue (`#0A84FF`) for focus/active states.
- Text: near-black (`#101113`) and muted gray (`#5B616E`) in day mode.
- Success/warn/error: modern, muted tones (`#24A148`, `#F5A623`, `#E5484D`).

### Spacing & Layout
- Use 24–32px padding on primary panels.
- Maintain consistent vertical rhythm (8px or 12px increments).
- Cards and list items should have at least 12–16px internal padding.

### Radius & Elevation
- Small radius: 8px, medium: 12px, large: 18px, extra large: 24px.
- Shadows are soft and blurred to evoke premium depth, not heavy lifts.

### Components
- **Buttons**: pill-shaped, solid for primary action, subtle outline for secondary.
- **Inputs**: soft border + gentle focus ring (3px with 15% alpha).
- **Cards**: elevated surfaces with subtle border and shadow.
- **Badges**: rounded pills with tinted backgrounds.
- **Modals**: large radius, layered shadows, and a blurred overlay.

### Iconography
- Avoid emoji or decorative icons in primary UI controls.
- Prefer simple, geometric toggles or monochrome icons.

## Global Dashboard Architecture

### Shared Workspace

All users interact with the same dataset:

- **No user-specific filtering** of companies, documents, or analyses.
- **Attribution is visible** (who uploaded, who initiated analysis).
- **Collaborative workflow** with shared, real-time updates.

### Attribution Display

- User name next to uploaded documents
- User name next to initiated analyses
- Timestamp of actions

## Login Page

### Purpose

The login page is the landing page during development and is the gateway to the shared dashboard.

### User Flow

1. User arrives on login page
2. User clicks **Sign in with Google**
3. OAuth consent screen opens
4. User authorizes access
5. User is redirected back to Tiger-Cafe
6. User lands in the Global Dashboard (two-panel layout)

### UI Requirements

#### Login Card
- Centered card containing a single Google login button
- Minimal distractions (no extra content)

#### Google OAuth Button
- Use Google branding guidelines
- Minimum size: **240px × 40px**
- Blue primary color: **#4285F4**
- Google logo left of text
- Hover: subtle elevation/shadow
- Active: slight press animation

#### Error Handling
- Toast or banner with user-friendly language
- Dismissible errors
- Common errors:
  - OAuth cancellation
  - Network error
  - Server error

#### Loading States
- Centered loading spinner
- “Signing you in…” text
- Prevent multiple clicks while in progress

## Global Dashboard Layout

### Two Adjustable Split Screens

- Vertical split with draggable divider
- Min/max widths: **20% / 80%**
- Default split: **50% / 50%**
- Split preference stored per user

### Left Panel (Navigation)

- Company list (default view)
- **Add Document** button at bottom
  - Changes to **Check Uploads** during active uploads
- Selecting a company shows company documents
- Selecting a document shows document details

### Right Panel (Content)

- Default: recent completed analysis list
- Company selected: company analysis dashboard
- Document selected: extracted data + progress view
  - Financial statements tables
  - Validation indicators
  - Operating vs. non-operating classification
  - Additional items table
  - Re-run and delete actions

### Day/Night Toggle

- Location: top-right in header/navbar
- Visual design: icon toggle (sun/moon) or switch
- **Day mode**
  - Background: #FFFFFF / #F5F5F5
  - Text: #212121 / #000000
- **Night mode**
  - Background: #121212 / #1E1E1E
  - Text: #E0E0E0 / #FFFFFF
- Transition: 200–300ms fade
- Preference stored in localStorage

## Phase 2: Document Upload & Classification UI

### Multi-Document Upload Flow

1. User clicks **Add Document**
2. Modal opens with drag-and-drop interface
3. User selects up to 10 PDFs
4. Modal closes immediately after selection
5. Uploads start in parallel (file I/O only)
6. Classification + indexing run sequentially
7. **Add Document** becomes **Check Uploads** with spinner
8. User opens upload progress view
9. Duplicate detection stops at classification with warning
10. If no duplicate, indexing continues automatically
11. After indexing, financial statement processing starts (if eligible)

### Upload Modal Requirements

- Drag-and-drop + manual file picker
- Clear limit indicator: “Upload up to 10 PDF documents”
- Visual drop zone with dashed border
- List of selected files + remove option
- **Upload** button triggers process

### Upload Progress View (Left Panel)

- List of all in-progress documents
- Each item shows:
  - Filename
  - Progress bar with milestones
  - Current status text

### Milestones & Status Indicators

**Milestones**
1. Uploading
2. Classification
3. Indexing

**States**
- Completed: green check
- Active: highlighted with animation
- Pending: muted/gray

### Duplicate Detection UX

- Progress halts at **Classification**
- Warning banner appears
- Shows existing document metadata
- **Replace & Index** button resumes pipeline

### Financial Statement Processing (Document View)

When a document is selected:

- Progress tracker shows **5 milestones**:
  1. Extracting balance sheet
  2. Classifying balance sheet
  3. Extracting income statement
  4. Extracting additional items
  5. Classifying income statement
- Real-time status: `checking`, `pending`, `in_progress`, `completed`, `error`, `not_found`
- Tables include validation status and operating/non-operating labels

#### 3. Document Status Indicators
- Status badges with color coding:
  - Pending: Gray badge "Pending"
  - Indexing: Blue badge with spinner "Indexing..."
  - Indexed: Green badge "Indexed"
  - Processing Analysis: Orange badge "Analyzing..."
  - Analysis Complete: Green badge "Complete"
  - Error: Red badge "Error" with tooltip showing error message
- Progress bar for indexing (0-100%)
- Icon indicators: Checkmark (complete), spinner (processing), X (error)
- Status tooltip on hover showing detailed status
- Real-time updates visible to all users

#### 4. Financial Analysis Trigger
- Button placement: In document row or company detail header
- Button label: "Run Analysis" or "Analyze Document"
- Confirmation dialog: "Start financial analysis for [Document Name]? This may take several minutes."
- Disabled state: Gray out button and show tooltip "Analysis already in progress" or "Analysis completed"
- Attribution display: Show "Analyzed by [User Name]" with timestamp after completion
- Real-time updates:
  - Show progress indicator when analysis starts
  - Display "Analysis in progress..." status
  - Update all users' views when analysis completes
  - Show notification toast when analysis finishes
