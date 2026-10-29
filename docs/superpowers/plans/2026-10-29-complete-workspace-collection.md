# Complete Workspace Collection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; final independent review required.

**Goal:** Broad seeded placement with physically completed demonstrations and honest dataset outcomes.
**Architecture:** Extend collection settings/proposal sampler, derive capture duration from verified rehearsal, and summarize persisted outcomes independently of file validation. Keep existing physical planner and transactional writer.
**Tech Stack:** Existing Python/MuJoCo/FastAPI and React/TypeScript/Playwright.
**Spec:** docs/superpowers/specs/2026-10-29-complete-workspace-collection.md

## Constraints / review focus
Legacy explicit settings retain meaning. Broad proposals never bypass rehearsal, table or containment constraints. Auto length does not truncate a verified plan. Counts cover retained episodes only. Test cleanup cannot touch active or unrelated jobs.

- [x] Add failing regressions for schema migration/defaults, broad seeded footprints/group containment, duration decision and old-job success counts.
- [x] Implement configuration, workspace proposals, automatic duration/rejection and persisted progress/outcome counters; validate tests and real workspace seed acceptance.
- [x] Add UI mode controls, duration warnings, success summaries and test-owned fixture archival. Browser regression checks default modes and explicit failed-output labeling.
- [x] Run relevant backend/browser/unit/build checks, archive known smoke fixtures, generate and inspect successful workspace episodes.
- [x] Independent review, documentation/evidence and local commit.

Pre-flight: sampler consumes Variation.position_mode; worker consumes duration_mode and plan.duration; UI uses those defaults and successful_episodes/unsuccessful_episodes from job API. Legacy migration occurs before schema validation. No interface conflicts.

Evidence: docs/VERIFICATION.md. Four backend regressions and new UI mode expectations failed before implementation; all passed afterward. 27 distinct relevant backend cases, 4 browser scenarios, 14 unit tests and build passed. Real local dataset retained 3/3 successful wide-placement tasks; final camera frames inspected. Final independent review: no actionable findings.
