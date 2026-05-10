# Microsoft Store Listing — Draft Copy

This is the paste-ready text for each free-text field in the Partner Center
submission form. Edit in place, then copy into the matching field at
submission time. Pair this with `CERTIFICATION_NOTES.md` (notes for the
cert team) and the assets in `logos/`.

---

## Properties → Product features (bulleted, ≤200 chars each, up to 20)

```
- One-click "Ready" alerts between dental workstations on a local network.
- Zero-configuration peer discovery — no server, no cloud, no accounts.
- Per-workstation station labels (Room 1, Doctor, Lab, etc.).
- 15 built-in alert sounds, per-recipient sound choice, per-workstation volume.
- Default-targets per station for one-tap multi-recipient sends.
- Three built-in visual themes (Modern Blue, Sage Clinic, Rose Quartz).
- System tray / menu-bar quick-send and show/hide.
- Local connection log for troubleshooting.
- Manual peer IP fallback for networks where UDP broadcast is blocked.
- Privacy-respecting: no analytics, no telemetry, no cloud — your data stays on your LAN.
```

---

## Store listing → Description (≤10,000 chars)

```
Chairside Ready Alert is a simple, private LAN messaging tool for dental
practices. With one click, a clinical assistant can let the doctor know
"Room 2 is ready" — and the doctor's PC pings, blinks, and brings the
window to the foreground. No server. No cloud account.

Pricing: $14.99 one-time purchase from the Microsoft Store. No subscription,
no recurring billing. Once purchased, the app installs on up to 10 Windows
devices linked to your Microsoft account — enough for an entire typical
dental practice from one purchase. Microsoft Store handles payment and
reinstall.

How it works
Every workstation runs the same app. Each one is given a station label
(Room 1, Room 2, Doctor, Lab, etc.). The app discovers the others on
your local network automatically and shows them in a one-tap send list.
Hit the button, the alert goes through. That's it.

Privacy and ownership
Chairside Ready Alert does not contact any cloud service, send analytics,
or transmit data outside your local network. Station labels and alert
messages travel only between devices on the same LAN. Your data stays
in your office.

Designed for dental offices
- One-click "Ready" alerts between rooms.
- 15 built-in alert sounds per workstation.
- Per-station volume control and visual theme.
- Default-targets so one tap can hit multiple rooms.
- Manual peer IPs for networks where broadcast discovery is blocked.
- System tray quick-send when the main window is hidden.

Important: not for emergencies
Chairside Ready Alert is an operational convenience tool. It is not
intended for emergencies, life-safety alerts, patient monitoring, or
clinical decision support. Always maintain independent clinical and
emergency communication procedures.

Data and privacy: see the linked privacy policy. Support questions:
support@fieldcrestdental.com
```

---

## Store listing → Short description / tag line (≤200 chars)

```
One-click LAN alerts between dental workstations. $14.99 one-time purchase covers up to 10 devices on your Microsoft account. Your data stays in your office.
```

---

## Store listing → What's new in this version (≤1,500 chars)

```
Pricing simplification: Chairside Ready Alert is now a one-time $14.99 USD purchase instead of a monthly subscription. Once you buy it, the app installs on up to 10 of your Microsoft account's Windows devices — no recurring billing, no trial expiration, no surprise charges. Same LAN-only peer-to-peer alerting, same privacy guarantees.
```

---

## Store listing → Search terms (up to 7)

```
dental
LAN
messaging
chairside
intercom
office
alert
```

---

## Store listing → Copyright and trademark info

Recommended (covers copyright + claims common-law trademark on the name and logo, no registrations needed):

```
© 2026 Fieldcrest Dental PC. All rights reserved. "Chairside Ready Alert" and the Chairside Ready Alert logo are trademarks of Fieldcrest Dental PC.
```

Shorter alternative if Partner Center's field is strict:

```
© 2026 Fieldcrest Dental PC. All rights reserved.
```

> **Why this is OK without filing anything:** Copyright is automatic
> the moment code is written — the © notice declares an existing right.
> Common-law trademark accrues automatically through use in commerce —
> "is a trademark of" or the ™ symbol can be used freely without
> registration. **Do not** use ® unless USPTO has actually registered
> the mark; using ® without registration is a federal violation.

---

## Store listing → Applicable license terms

You have two options here. Either works for Partner Center.

**Option A (recommended): paste a URL**
```
https://ayodoood.github.io/Chairside-Ready-Alert/EULA.html
```
Cleaner, easier to update later (edit `EULA.md` in the repo, push, the URL serves the new version).

**Option B: paste the full EULA text**
Copy the body of `EULA.md` (between the frontmatter and the closing
italic disclaimer). It's ~6,500 characters, comfortably under
Partner Center's 10,000-char limit.

> ⚠️ The EULA is a starter template. Have a healthcare-IT attorney
> review before you ship — particularly the safety carve-out, the
> governing-law placeholder, and any HIPAA/HITECH considerations
> that apply to your jurisdiction.

---

## Store listing → Developer-defined info

| Field | Value |
|---|---|
| Developer name | Fieldcrest Dental PC |
| Support contact info | support@fieldcrestdental.com |
| Website | https://ayodoood.github.io/Chairside-Ready-Alert/ |

---

## Properties → System requirements

| Field | Value |
|---|---|
| Minimum hardware | Standard Windows 10/11 PC, no special requirements |
| Recommended hardware | Same |
| Minimum OS version | Windows 10 build 17763.0 or higher |
| Network | Local area network (LAN) connection on the same subnet as other workstations running the app |

---

## Properties → Product declarations to check

- [x] This app accesses, collects, or transmits personal information (station label, alert messages — LAN-only)
- [x] This app uses local area network (LAN) connectivity
- [ ] (do NOT check) Uses internet/cloud
- [ ] (do NOT check) Includes advertising
- [ ] (do NOT check) Camera, microphone, location, contacts, etc.

---

## Pricing and availability — recommended values

| Field | Value |
|---|---|
| Base price | **$14.99 USD** (one-time purchase) |
| Markets | All available markets |
| Audience | Public |
| Free trial | None (or 7-day trial at the listing level if you want to offer one — Microsoft Store handles trial expiry) |
| Sale pricing | None |
| Schedule | "Publish as soon as certification passes" |
| Organizational licensing (volume) | Allow |
| Family-shared license | Off |

### Note on the previous subscription Add-ons

Earlier submissions (v1.0.20–v1.0.28) used a free-app + subscription Add-on
model. That commerce path got stuck in a `PEX-CatalogAvailabilityDataNotFound`
state on Microsoft's catalog backend that we could not unstick. v1.0.29
pivots to one-time paid-app pricing at the listing level, which uses a
different commerce code path (Get/Buy on the listing) and bypasses the
broken Add-on catalog state entirely.

The two existing Add-ons under this app
(`ChairsideReadyAlert.Subscription.Monthly` and
`ChairsideReadyAlert.SubV2.Monthly`) should be retired once v1.0.29 is
live: each Add-on → Update → Pricing and availability → Visibility =
Hidden, **Stop Acquisition off** (Stop Acquisition was observed to
interfere with catalog reconciliation). Submit each.

---

## Age rating questionnaire — expected answers

| Question | Answer |
|---|---|
| Violence / blood / gore | None |
| Sexual content | None |
| Profanity | None |
| Substance use | None |
| Gambling | None |
| User-to-user communication | **Yes** (LAN-only labeled alerts) |
| Shares user location | No |
| Personal info collected | No (LAN-only, doesn't leave the network) |
| In-app purchases | No (paid app, no in-app purchases as of v1.0.29) |
| Unrestricted internet | No |

Expected resulting rating: **Everyone / 3+**.

---

## Submission options

| Field | Value |
|---|---|
| Publishing | "Publish as soon as it passes certification" |
| Notes for certification | Paste the block from `CERTIFICATION_NOTES.md` |
| Restricted capabilities | None |

---

## Reminder: Things you still have to do by hand

1. Reserve the app name `Chairside Ready Alert` in Partner Center. (Done.)
2. Capture **3+ screenshots** at 1366×768 or 1920×1080 of the EXE running on a Windows machine. There is no way to fake these from macOS — they have to be real shots of the running app on Windows.
3. Upload the three architecture MSIX bundles from the latest CI run page.
4. Set Pricing and availability → Base price → **$14.99 USD**.
5. Retire the two stuck subscription Add-ons (Hidden visibility, Stop Acquisition off).
