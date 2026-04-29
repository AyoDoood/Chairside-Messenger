# Microsoft Store Submission — MSIX path

This guide covers the **MSIX** submission path (replaces the older Win32 EXE
flow). The build pipeline produces three architecture-specific `.msix` files
on every tagged release (v*); the rest is filled in by hand in Partner
Center.

## What changed vs the old EXE path

- No "hosted installer URL" anymore. Microsoft Store distributes the package.
- Updates are 100% Store-managed. The app's in-built update check is
  already gated off in frozen builds, so this just works.
- First-run firewall prompt is gone — `privateNetworkClientServer` capability
  is honored automatically.
- Apps & Features registration, Start Menu shortcut, and uninstall plumbing
  are all Store-managed too.

The **direct-installer path** (`install_chairside_ready_alert.ps1` +
`Install Chairside Ready Alert.bat` + the macOS `.command`) is unchanged
and continues to work for non-Store deployments.

---

## One-time setup: paste the three Partner Center identity values

MSIX packages are cryptographically bound to your Partner Center reservation.
Three string values must match exactly. They live at:

> **Partner Center → Apps and games → Chairside Ready Alert → Product
> management → App identity** (or "Product Identity" depending on UI variant)

| Partner Center field | Goes into `AppxManifest.xml` as |
|---|---|
| Package/Identity/Name | `<Identity Name="..." />` |
| Package/Identity/Publisher | `<Identity Publisher="..." />` |
| Package/Properties/PublisherDisplayName | `<PublisherDisplayName>...</PublisherDisplayName>` |

Open `Windows Store Submission/AppxManifest.xml`. Replace the three
`REPLACE_WITH_PARTNER_CENTER_*` placeholders with the values from Partner
Center. Commit and push. The other two placeholders (`VERSION_PLACEHOLDER`,
`ARCH_PLACEHOLDER`) are filled in automatically by the build — leave them.

> ⚠️ Do NOT use `®` or `CN=...` strings you make up. Partner Center has
> already generated these for your account; the only acceptable values are
> the ones it shows you.

---

## Build the MSIX files

After committing the three identity values, push a tag:

```bash
git tag v1.0.13     # or whatever the next release number is
git push origin v1.0.13
```

The GitHub Actions workflow `Build Windows EXE` runs and produces, for each
architecture, both:

- `ChairsideReadyAlert-<arch>` (the unchanged onedir folder for the
  direct-installer path)
- `ChairsideReadyAlert-<arch>-msix` (the new MSIX file for Partner Center)

Watch the run at:

> https://github.com/AyoDoood/Chairside-Ready-Alert/actions

When green, the run page shows six artifacts at the bottom (three folders +
three `.msix`). Download the three `-msix` artifacts.

---

## Submit to Partner Center

1. Sign in to Partner Center → **Apps and games** → click **Chairside
   Ready Alert** (your reserved name).
2. Start a new submission. The Partner Center UI has been redesigned and
   no longer has a "Submissions" tab — look for **Create new submission**,
   **Releases**, or a similarly-labeled action on the app's overview page.
3. On the **Packages** step, upload the three `.msix` files (one per
   architecture). Partner Center auto-detects the architecture from each
   manifest.
4. Other sections (Pricing, Properties, Age rating, Store listing, Privacy
   policy URL, Notes for certification) are inherited from the app product
   itself. Fill in any sections marked incomplete using values from
   `STORE_LISTING_DRAFT.md` and `CERTIFICATION_NOTES.md`.
5. Submit for certification. Typical turnaround is 1–3 business days.

---

## What gets bundled into each .msix

- The full PyInstaller `--onedir` output (the EXE plus its `_internal`
  folder of Python runtime + Tcl/Tk + bundled site-packages).
- `Assets/` folder with six logo PNGs renamed to MSIX standards
  (Square44x44Logo, StoreLogo, Square71x71Logo, Square150x150Logo,
  Wide310x150Logo, Square310x310Logo).
- `AppxManifest.xml` with the architecture and version filled in at
  build time.

The package is **unsigned**. Microsoft Store re-signs every submission
with its own certificate during certification — you don't need to provide
or maintain a code-signing certificate for Store submissions. (For
sideload-testing on a dev machine, you'd need a self-signed cert, but
Store submission doesn't.)

---

## Local sideload testing (optional)

If you want to install the .msix on a Windows machine **before** submitting,
you'll need to either self-sign it or enable developer mode and sideload it
unsigned. Both options are documented in the Microsoft sideload-MSIX guide.
For most workflows, just submit and let Microsoft's certification team
verify it runs — that's effectively your test.

---

## Capabilities declared

| Capability | Why |
|---|---|
| `runFullTrust` (restricted) | Required for any PyInstaller-bundled / desktop-bridge app. Auto-approved at submission for personal Microsoft Store accounts. |
| `privateNetworkClientServer` | LAN UDP broadcast (50506) and TCP messaging (50505). |

No `internetClient` capability — the Store build makes no outbound internet
calls (the in-app update path is gated off in frozen builds, and there's no
telemetry/analytics).
