// StoreHelper.exe — Microsoft Store purchase shim for Chairside Ready Alert.
//
// The parent app is a Python/Tkinter program packaged as MSIX. Calling
// Windows.Services.Store.StoreContext.RequestPurchaseAsync from a Win32
// desktop host has two requirements that Python alone cannot meet:
//
//   1. The host must call IInitializeWithWindow.Initialize(hwnd) with a
//      same-process HWND before the call. Cross-process HWNDs do not work
//      — the Store SDK validates the anchor window's process identity.
//   2. The anchor window must have a running message pump while
//      RequestPurchaseAsync is in flight, otherwise the purchase overlay
//      never renders and the call hangs.
//
// This binary owns its own invisible WinForms window, runs Application.Run
// to drive a real message pump, kicks off the Store call from the form's
// Shown event, and closes the form when the async call completes. The
// Store overlay anchors to this same-process HWND and renders centered on
// screen (because the form is minimized).
//
// Python invokes this binary via subprocess, parses stdout, and uses the
// exit code as the success/fail signal. The HWND argument is accepted but
// ignored (kept for backward compatibility with v1.0.23–v1.0.25 callers).
//
// Usage: StoreHelper.exe <product_id> [hwnd_decimal_unused]
//   Exit 0  — purchase succeeded or already owned by the user.
//   Exit 1  — Store returned a non-success status (cancelled, network, etc.).
//   Exit 2  — bad command-line arguments.
//   Exit 3  — exception thrown inside the helper.
// Stdout : "STATUS=<StorePurchaseStatus>" and optionally "EXTENDED_ERROR=<text>".
// Stderr : usage message or "EXCEPTION: <Type>: <message>".

using System;
using System.Threading.Tasks;
using System.Windows.Forms;
using Windows.Services.Store;

namespace ChairsideReadyAlert.StoreHelper;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length < 1 || args.Length > 2)
        {
            Console.Error.WriteLine("usage: StoreHelper.exe <product_id> [hwnd_decimal_unused]");
            return 2;
        }

        string productId = args[0];
        int exitCode = 3;

        // Invisible same-process anchor window. The Store overlay needs an HWND
        // owned by the calling process; cross-process HWNDs from the parent app
        // do not work for IInitializeWithWindow.
        var form = new Form
        {
            Opacity = 0.0,
            ShowInTaskbar = false,
            FormBorderStyle = FormBorderStyle.None,
            StartPosition = FormStartPosition.CenterScreen,
            WindowState = FormWindowState.Minimized,
            Width = 1,
            Height = 1,
        };

        async void OnShown(object? sender, EventArgs e)
        {
            try
            {
                StoreContext ctx = StoreContext.GetDefault();
                WinRT.Interop.InitializeWithWindow.Initialize(ctx, form.Handle);

                StorePurchaseResult result = await ctx.RequestPurchaseAsync(productId);
                Console.WriteLine($"STATUS={result.Status}");
                if (result.ExtendedError is not null)
                {
                    string msg = result.ExtendedError.Message.Replace("\r", " ").Replace("\n", " ");
                    Console.WriteLine($"EXTENDED_ERROR={msg}");
                }

                exitCode = result.Status switch
                {
                    StorePurchaseStatus.Succeeded => 0,
                    StorePurchaseStatus.AlreadyPurchased => 0,
                    _ => 1,
                };
            }
            catch (Exception ex)
            {
                string msg = ex.Message.Replace("\r", " ").Replace("\n", " ");
                Console.Error.WriteLine($"EXCEPTION: {ex.GetType().Name}: {msg}");
                exitCode = 3;
            }
            finally
            {
                form.Close();
            }
        }

        form.Shown += OnShown;
        Application.Run(form);
        return exitCode;
    }
}
