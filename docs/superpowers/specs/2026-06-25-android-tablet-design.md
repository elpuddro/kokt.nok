# kokt.nok Android Tablet — Design Spec

**Date:** 2026-06-25
**Status:** Approved

## Goal

Deliver a full-featured Android tablet version of kokt.nok via Google Play. Feature parity with the desktop (Windows/Linux) app. Maximum code reuse from the existing Tauri v2 codebase. UI adapted for tablet touch interaction and both portrait and landscape orientations — same design language, not a redesign.

---

## Architecture

**Approach:** Tauri v2 Android build — same Rust backend, same SvelteKit frontend, compiled to ARM via Android NDK. The SvelteKit static build runs in Android's System WebView.

**Database:** `kokt.db` (17 MB) is bundled in the APK as a Tauri resource (`kokt-bundle.db`). On first launch, the app copies it to `app_data_dir()/kokt.db` (writable). All subsequent reads and writes go to that copy. The bundled file is the read-only seed — user-created recipes accumulate in the writable copy. Reinstalling the app loses user-created recipes (same behavior as desktop reinstall — acceptable for v1).

**User data** (favorites, shopping list, meal plan, notes, inventory, health profile) lives in `tauri-plugin-store` JSON files, which already use `app_data_dir()` on all platforms — no changes needed.

**`kbilde://` custom URI protocol** works on Android as-is via Tauri v2's URI scheme registration.

---

## Backend Changes (Rust — `src-tauri/src/lib.rs`)

### `db_path()` — Android branch
Add `#[cfg(target_os = "android")]` branch that always returns `app_data_dir()/kokt.db`, skipping the exe-relative and resource-dir lookups used on desktop.

### `ensure_db()` — new function, called at startup
1. Check if `app_data_dir()/kokt.db` exists.
2. If not: read `kokt-bundle.db` from resource dir via `app.path().resolve(..., BaseDirectory::Resource)`, write bytes to `app_data_dir()/kokt.db`.
3. Called once inside `run()` before the invoke handler is registered.

### `open()` — read-write on Android
On desktop, the DB is opened read-only (`SQLITE_OPEN_READ_ONLY`). On Android, open read-write so recipe create/edit/versioning commands can write to it. Gate with `#[cfg(target_os = "android")]`.

### `cook_mode()` — Android wakelock
Add `#[cfg(target_os = "android")]` branch that acquires/releases `SCREEN_BRIGHT_WAKE_LOCK` via JNI using Tauri v2's `android_binding` mechanism (or `tauri-plugin-prevent-sleep` community plugin if available and stable). The Windows and Linux branches are unchanged.

### Existing platform gates
`windows-sys` and `zbus` dependencies are already gated to their respective platforms — Android builds cleanly with no changes.

---

## Config Changes

### `tauri.conf.json`
- Keep existing `bundle` config (NSIS targets) untouched — desktop builds are unaffected.
- Android icons and splash are configured in `gen/android/` (scaffolded by `cargo tauri android init`), not in `tauri.conf.json`.
- CSP already includes `https://kbilde.localhost` — no changes needed.

### `Cargo.toml`
- Add Android wakelock dependency gated to `cfg(target_os = "android")` — either JNI directly or a community plugin.

### `gen/android/` (new, gitignored keystore)
- Scaffolded by `cargo tauri android init`.
- Release signing configured in `gen/android/app/build.gradle` referencing a keystore file stored outside the repo.
- Keystore must be kept permanently — losing it prevents future Play Store updates.

---

## Frontend Changes (SvelteKit / CSS)

The overall design language (colors, themes, seasonal decorations, card style, typography) is unchanged. Changes are layout and sizing only.

### Navigation
- **Landscape (tablet default):** existing sidebar nav likely already visible — verify and keep.
- **Portrait:** add a collapsible drawer triggered by a hamburger/menu button. Sidebar collapses to an overlay drawer. No new Svelte components — CSS `@media (orientation: portrait)` rules control visibility.

### Touch targets
- All interactive elements (buttons, list rows, icon actions) audited to meet minimum 44×44 dp tap size.
- Increase padding on compact desktop elements where needed — CSS only, no component changes.

### Font sizes
- Audit for fixed `px` font sizes; convert to `rem` where found so Android system font scale settings are respected.

### Soft keyboard handling
- Recipe create/edit forms: add `padding-bottom: env(keyboard-inset-height, 0px)` (or equivalent resize listener) so the soft keyboard doesn't obscure input fields.

### Orientation reflow
- CSS media queries for `(orientation: portrait)` and `(orientation: landscape)` handle layout differences.
- Recipe grid: adjusts column count per orientation (e.g. 2 columns portrait, 3–4 landscape).
- No new Svelte components needed.

---

## Features — Full Parity

All existing features are carried over:

| Feature | Notes |
|---|---|
| Recipe browsing + search | Unchanged |
| Recipe detail view | Unchanged |
| Recipe create / edit / versioning | DB opened read-write on Android |
| Cook mode + timers | Wakelock adapted for Android |
| Meal planner | Unchanged |
| Shopping list | Unchanged |
| Inventory / "hva kan jeg lage" | Unchanged |
| Diet / allergy filters | Unchanged |
| Health profile | Unchanged |
| Favorites | Via plugin-store, unchanged |
| Notes per recipe | Via plugin-store, unchanged |
| Themes + seasonal decorations | Unchanged |
| Holiday detection | Unchanged (pure Rust, no platform deps) |

---

## Google Play Distribution

| Item | Value |
|---|---|
| Package ID | `no.kokebok.app` |
| App name | Kokebok |
| Version | 1.0.0, versionCode 1 |
| Build format | AAB (`cargo tauri android build --aab`) |
| Target API | 34+ (Android 14, Tauri v2 default) |
| Category | Food & Drink |
| Content rating | Everyone |
| Internet permission | Remove (offline app) |
| Privacy policy | Required — simple page hosted on GitHub Pages |
| Store assets | Tablet + phone screenshots, short/long description in Norwegian |

**Signing:** One-time keystore generation. Store keystore file securely outside the repo. Configure in `gen/android/app/build.gradle`.

**Release cadence:** New APK/AAB version when features are added, same as desktop. Initial Play review: 1–3 days. Updates: typically faster.

---

## What Is Not in Scope (v1)

- Phone form factor (tablet only)
- OTA database updates (new recipes require app update)
- Cloud sync of user data
- Backup/restore of user-created recipes
- iOS
