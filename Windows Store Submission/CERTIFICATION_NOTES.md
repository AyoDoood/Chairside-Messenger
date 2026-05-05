# Notes for Microsoft Store Certification

This file contains the exact text to paste into the **"Notes for certification"**
field of the Partner Center submission, plus context for what the certification
team should and should not expect to see.

The app is a LAN messaging tool gated behind a Microsoft Store subscription
Add-on (`ChairsideReadyAlert.Subscription.Monthly`). Two facts the reviewer
must understand before testing:

1. The first screen shown after install is a subscription welcome / paywall.
   All app functionality is behind it. The reviewer cannot reach the LAN
   messaging UI without an active subscription on the test Microsoft account.
2. Even with an active subscription, the LAN messaging features REQUIRE TWO
   OR MORE DEVICES on the same local subnet and cannot be exercised on a
   single test VM.

Both of those would cause a naïve "the app doesn't seem to do anything"
rejection under policy 10.1.2.7. The notes below give the reviewer a test
path that exercises everything that CAN be tested in a single-VM, no-Store-
account test environment.

---

## Paste-into-Partner-Center text

```
Chairside Ready Alert is a LAN-based messaging tool for dental practices, gated behind a Microsoft Store subscription Add-on (ChairsideReadyAlert.Subscription.Monthly, $1.99 / month with 7-day free trial). Microsoft Store handles all billing — the app only reads "is the subscription active?" via the Store SDK and gates its UI accordingly.

Two things the reviewer needs to know before testing:

1. The FIRST screen after install is a welcome / paywall window. All app functionality is behind it. This is intentional and is the entire revenue model.
2. The LAN messaging core feature requires TWO OR MORE DEVICES on the same local subnet and cannot be exercised on a single test VM.

Test path that works in a single-VM environment without a Store subscription:

A. Launch the app from the Start menu.
B. The "Welcome to Chairside Ready Alert" window appears with a Modern Blue theme: title, pricing line ("Free for 7 days. $1.99 / month after"), body text describing the LAN messaging product, and three buttons (Start 7-day free trial / Restore purchases / Quit). Verify the window renders cleanly with no clipped text.
C. Click "Start 7-day free trial". The bundled StoreHelper.exe (a small C# binary in the same MSIX package) invokes Windows.Services.Store.StoreContext.RequestPurchaseAsync, which opens the standard Microsoft Store purchase overlay. Closing that overlay without buying returns to the welcome window — verify no crash.
D. Click "Restore purchases". With no active subscription on the signed-in account, the welcome window shows "No active subscription found on this Microsoft account." — verify the message displays and the buttons re-enable.
E. Click "Quit". The app exits cleanly.

That covers everything that can be exercised without a paid subscription. The behavior beyond the paywall (LAN peer discovery on UDP 50506, alert delivery on TCP 50505, station labels, themes, tray menu) is unchanged from the previously approved v1.0.20 build and cannot be reached without an active subscription on the test account.

Bundled binaries:
- ChairsideReadyAlert.exe — the Python/Tkinter app (PyInstaller --onedir).
- StoreHelper.exe — small self-contained .NET 8 helper that performs the IInitializeWithWindow handshake the Store SDK requires for purchase calls (Python's winrt projection cannot reach IInitializeWithWindow because it's classic COM). The helper has no UI of its own and exits immediately after the Store call completes; it makes no internet calls beyond what the Microsoft Store SDK does.

Network: LAN UDP broadcast on port 50506 (peer discovery) and LAN TCP on port 50505 (alert delivery). No outbound internet calls in normal operation. The Store build has no in-app self-update — updates are delivered through the Store channel only.

The runFullTrust restricted capability is declared because this is a Python/Tkinter desktop app packaged as MSIX (desktop bridge). Standard for any PyInstaller-bundled MSIX submission — the bundled Python interpreter and Tkinter GUI cannot run inside UWP sandboxing.

Privacy policy: https://ayodoood.github.io/Chairside-Ready-Alert/PRIVACY_POLICY.html
FAQ:            https://ayodoood.github.io/Chairside-Ready-Alert/FAQ.html
Support:        support@fieldcrestdental.com
```

---

## Why this matters

Subscription-gated apps where the paywall is the first screen are a known
trip-hazard for cert review under policy 10.1.2.7 ("App must be fully
functional"). The reviewer installs, sees a paywall, can't subscribe
(test accounts don't always have a payment method, or the reviewer
wasn't given one), and concludes "this app doesn't do anything." The
notes above pre-empt that by:

- Stating up front that the paywall IS the entry point (not a bug).
- Giving a step-by-step test path that completes inside the paywall
  itself — every step is verifiable without subscribing.
- Acknowledging that LAN messaging cannot be tested in a single-VM
  environment, so the reviewer doesn't search for it past the paywall.

The first rejection of v1.0.27 (under 10.1.2.7) used the old cert notes
that pre-dated the paywall. The reviewer was told to test peer messaging
they couldn't reach. Replacing the notes block with the one above is
sufficient — no app changes needed.

## What you fill in elsewhere on the submission form

| Field | Value |
|---|---|
| App name | Chairside Ready Alert |
| Category | Productivity |
| Subcategory | Communication (closest match) |
| Privacy policy URL | https://ayodoood.github.io/Chairside-Ready-Alert/PRIVACY_POLICY.html |
| Website URL | https://github.com/AyoDoood/Chairside-Ready-Alert  ⚠️ see "URL safety flag" below |
| Support contact | support@fieldcrestdental.com |
| System requirements | Windows 10 version 17763.0 or higher |
| Architectures submitted | x64, x86, arm64 (separate packages — do NOT mark as `neutral`) |
| Age rating | Submit IARC questionnaire; expect ~3+ (no objectionable content) |
| Pricing | Free download; subscription Add-on at $1.99 / month with 7-day trial |

## URL safety flag (`fieldcrestdental.com`)

Microsoft Defender SmartScreen flagged the website URL on the Store
listing. SmartScreen rejects URLs for any of:

- Recently registered domain (low trust score by default).
- Parked / "under construction" page with no real content.
- Hosted on a provider that's been previously abused.
- A genuine malicious classification (rare for legitimate dental
  practice sites).

**Fastest fix: replace the website URL field on the listing with one
that already has SmartScreen reputation:**

- `https://github.com/AyoDoood/Chairside-Ready-Alert` (the project repo
  — high SmartScreen trust because GitHub is universally allowlisted),
  or
- `https://ayodoood.github.io/Chairside-Ready-Alert/` (the GitHub Pages
  documentation site — also GitHub-hosted, high trust).

Either is sufficient and matches what the existing
`STORE_LISTING_DRAFT.md` already lists as the recommended Website value.
Resubmit with the swapped URL and the SmartScreen flag clears.

**If you specifically want `fieldcrestdental.com` on the listing:**
verify the site is actually live with substantive content (not parked),
then request a SmartScreen review at
`https://www.microsoft.com/en-us/wdsi/filesubmission/exemption` —
classify the URL, explain the legitimate use, wait 1-3 business days
for a manual review.

## Capabilities to declare in the manifest

For an EXE/onedir Win32 submission:

- **internetClient** — NOT required. The Store EXE does not make outbound
  internet connections. Declaring it would needlessly trigger more
  permissions warnings.
- **privateNetworkClientServer** — REQUIRED. The app sends UDP broadcasts
  and accepts inbound TCP connections on the local network.

If Partner Center asks about specific capabilities at submission time,
declare only `privateNetworkClientServer` (and no internet capability).
