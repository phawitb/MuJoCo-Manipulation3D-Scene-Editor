# Pointer Placement and Cup Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Artifact-free object dragging, a curated library and a physical cup-to-plate example.
**Architecture:** React pointer capture drives a shared placement cursor and viewport raycasts. Preserve legacy API asset definitions. Extend measured contact-only grasp planning for exposed upright handles and safe withdrawal.
**Tech Stack:** React/Three.js, Python/MuJoCo, Playwright/pytest.
**Spec:** docs/superpowers/specs/2026-10-24-pointer-extraction.md

## Global Constraints
No invisible attachment or object teleportation during execution. Preserve live scenes. Only IKEA and cube in the visible library. User authorized autonomous implementation/testing/push.

## Review Focus
- Pointer capture over controls, Escape, cancellation/outside release and repeat drags.
- Legacy saved scenes/API retain mesh and old asset compatibility.
- Source utensil really rests inside cup and is lifted clear before transfer.
- Opposing contacts, passive drops and physical destination support remain required.
- All original examples, moved objects and bounded planning remain supported.

### Task 1: Pointer placement and library
- [x] RED browser tests: no native dragstart, only five library assets, ghost before drop, cancel/outside/no duplicate placement.
- [x] Implement pointer capture in Library.tsx, shared drag state in App.tsx and raycast/commit in Viewport.tsx. Filter displayed assets only.
- [x] GREEN browser suite, unit/build checks; commit.

### Task 2: Cup extraction
- [x] RED initial support/extraction test with spoon in cup and plate target.
- [x] Add example11 in examples.py; generalize policy grasp frame and withdrawal for measured upright handles.
- [x] Run contact tests, all examples, audit/render new example, full suites; commit.

### Task 3: Review and integrate
- [x] Independent final review, fix important findings with regressions, preserve results/decisions in verification docs, push main.
