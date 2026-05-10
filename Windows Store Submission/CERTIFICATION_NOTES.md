# Notes for Microsoft Store Certification

This file contains the exact text to paste into the **"Notes for certification"**
field of the Partner Center submission, plus context for what the certification
team should and should not expect to see.

The app is a LAN messaging tool sold as a **one-time paid app** at $14.99 USD
on the Microsoft Store. There is no subscription, no in-app purchase, no
paywall window inside the app. Microsoft Store gates installation via the
standard Get/Buy flow at the listing level — only customers who have paid
can install. The app launches directly to its main UI on first run.

The LAN messaging core feature requires TWO OR MORE DEVICES on the same local
subnet and cannot be exercised on a single test VM. Reviewers can only
confirm the app launches, renders, and quits cleanly in a single-VM
environment.

---

## Paste-into-Partner-Center text

```
Chairside Ready Alert is a LAN-based messaging tool for dental practices, sold as a one-time paid app at $14.99 USD. There is no subscription, no in-app purchase, and no paywall inside the app. Microsoft Store handles purchase via the standard Get/Buy flow at the listing level.

The LAN messaging core feature requires TWO OR MORE DEVICES on the same local subnet and cannot be exercised on a single test VM.

In a single-VM test environment, please confirm only:

1. The app launches and the main window renders.
2. The tray icon appears in the notification area.
3. The Settings menu opens.
4. Right-click on the tray icon shows: Send Ready, Show Main Window, Hide Main Window, Close.
5. Selecting "Close" from the tray menu shuts the app down cleanly.

An empty peer list and inability to send/receive alerts are EXPECTED on a single-machine test — no peer device, nothing to message.

Network: the app uses LAN UDP broadcast on port 50506 and LAN TCP on 50505. It makes no outbound internet connections in normal operation. The Store build has no in-app self-update; updates are delivered through the Store channel only.

The runFullTrust restricted capability is declared because this is a Python/Tkinter desktop app packaged as MSIX (desktop bridge). Standard for any PyInstaller-bundled MSIX submission — the bundled Python interpreter and Tkinter GUI cannot run inside UWP sandboxing.

Privacy policy: https://ayodoood.github.io/Chairside-Ready-Alert/PRIVACY_POLICY.html
Support:        support@fieldcrestdental.com
```

---

## What changed vs. previous submissions (context for reviewers)

Earlier submissions (v1.0.20 – v1.0.28) used a "free download + subscription
Add-on" model. The Add-on commerce path was stuck in a persistent
`PEX-CatalogAvailabilityDataNotFound` backend state in Microsoft's commerce
catalog that did not respond to any configuration attempted (multiple
visibility / audience settings on the parent app, two separately-published
Add-ons with distinct Product IDs, two Microsoft accounts, full clock and
cache resets). Microsoft Q&A / Partner Center support was unable to be
reached due to Engage Center routing.

v1.0.29 pivots to **one-time paid at $14.99**. This uses the standard
Microsoft Store listing-level pricing (the Get/Buy button on the listing),
not an Add-on. The app no longer has a paywall window, no longer ships a
StoreHelper.exe binary, and no longer calls
`Windows.Services.Store.StoreContext.RequestPurchaseAsync`. It is
functionally identical to the previously-approved v1.0.20 build with the
welcome / paywall removed and updates / bug fixes applied.

The two existing in-app subscription Add-ons under this app
(`ChairsideReadyAlert.Subscription.Monthly` and
`ChairsideReadyAlert.SubV2.Monthly`) will be retired (Hidden visibility,
Stop Acquisition off — Stop Acquisition was observed to interfere with
catalog reconciliation in earlier debugging) once v1.0.29 is approved
and live.

## What you fill in elsewhere on the submission form

| Field | Value |
|---|---|
| App name | Chairside Ready Alert |
| Category | Productivity |
| Subcategory | Communication (closest match) |
| Privacy policy URL | https://ayodoood.github.io/Chairside-Ready-Alert/PRIVACY_POLICY.html |
| Website URL | https://ayodoood.github.io/Chairside-Ready-Alert/ |
| Support contact | support@fieldcrestdental.com |
| System requirements | Windows 10 version 17763.0 or higher |
| Architectures submitted | x64, x86, arm64 (separate packages — do NOT mark as `neutral`) |
| Age rating | Submit IARC questionnaire; expect ~3+ (no objectionable content) |
| **Pricing** | **$14.99 USD, one-time purchase** |
| Free trial | (your call — Microsoft Store supports 7-day or 30-day trial periods at the listing level. None required.) |
| Markets | All available worldwide |
| Audience / Visibility | Public (or Hidden if you still want soft-launch) |

## Capabilities to declare in the manifest

For an EXE/onedir Win32 submission:

- **internetClient** — NOT required. The Store EXE does not make outbound
  internet connections. Declaring it would needlessly trigger more
  permissions warnings.
- **privateNetworkClientServer** — REQUIRED. The app sends UDP broadcasts
  and accepts inbound TCP connections on the local network.

If Partner Center asks about specific capabilities at submission time,
declare only `privateNetworkClientServer` (and no internet capability).
