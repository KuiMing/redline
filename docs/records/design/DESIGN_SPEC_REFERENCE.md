# DESIGN.md Specification Reference

Source: https://github.com/google-labs-code/design.md

## Purpose
DESIGN.md is a structured format for describing a visual identity to coding agents.
It combines:

1. YAML front matter (machine-readable design tokens)
2. Markdown prose (human-readable design rationale)

The tokens define exact values. The prose explains intent and usage.

---

## File Structure

A DESIGN.md file contains two layers:

---
YAML FRONT MATTER
---

Required structure example:

name: <string>
description: <string> (optional)

colors:
  <token-name>: "#HEX"

typography:
  <token-name>:
    fontFamily: <string>
    fontSize: <dimension>

rounded:
  <scale>: <dimension>

spacing:
  <scale>: <dimension>

components:
  <component-name>:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: 12px

---

## Supported Token Types

Color: "#1A1C1E"
Dimension: 16px, 1rem, -0.02em
Token Reference: {colors.primary}
Typography object:
  fontFamily
  fontSize
  fontWeight
  lineHeight
  letterSpacing

---

## Required Section Order (Markdown Body)

1. Overview
2. Colors
3. Typography
4. Layout
5. Elevation & Depth
6. Shapes
7. Components
8. Do's and Don'ts

Sections are optional but must follow this order if present.

---

## CLI Tools

Lint:
  npx @google/design.md lint DESIGN.md

Diff:
  npx @google/design.md diff DESIGN.md DESIGN-v2.md

Export:
  npx @google/design.md export --format tailwind DESIGN.md
  npx @google/design.md export --format dtcg DESIGN.md

Spec:
  npx @google/design.md spec

---

## Lint Rules

- broken-ref (error)
- missing-primary (warning)
- contrast-ratio (warning)
- orphaned-tokens (warning)
- token-summary (info)
- missing-sections (info)
- missing-typography (warning)
- section-order (warning)

---

This file is stored as a reference baseline for building a DESIGN.md-driven UI system in the Redline project.
