package io.apex.standalone;

import android.webkit.WebView;

final class EngineHelp {
    private EngineHelp() {}

    static void showEngineFailed(WebView webView, String detail) {
        String extra = detail == null || detail.isEmpty() ? "" : "<p><code>" + escape(detail) + "</code></p>";
        String html =
                "<!doctype html><html><head><meta charset=utf-8>"
                + "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "body{margin:0;padding:24px;background:#070b13;color:#eef4ff;font:15px/1.5 sans-serif}"
                + "h1{color:#63e6ff;font-size:22px}"
                + ".box{border:1px solid #263651;border-radius:12px;padding:16px;margin:16px 0;background:#0e1625;color:#b9c8dc}"
                + "code{color:#63e6ff}"
                + "</style></head><body>"
                + "<h1>On-device engine did not start</h1>"
                + extra
                + "<div class=\"box\"><p><strong>Try:</strong></p>"
                + "<ol><li>Force-stop APEX → reopen → wait up to 3 minutes on first launch</li>"
                + "<li>Settings → <strong>Desktop computer</strong> and enter your PC URL "
                + "(run <code>apex mobile</code> on the PC, same Wi‑Fi)</li>"
                + "<li>Reinstall the latest <code>apex-mobile.apk</code> from GitHub Actions</li>"
                + "</ol></div></body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    static void showRemoteFailed(WebView webView, String url) {
        String html =
                "<!doctype html><html><head><meta charset=utf-8>"
                + "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "body{margin:0;padding:24px;background:#070b13;color:#eef4ff;font:15px/1.5 sans-serif}"
                + "h1{color:#63e6ff;font-size:22px}"
                + "p,li{color:#b9c8dc}"
                + "code{background:#131e30;padding:2px 6px}"
                + ".box{border:1px solid #263651;border-radius:12px;padding:16px;background:#0e1625}"
                + "</style></head><body>"
                + "<h1>Desktop server not reachable</h1>"
                + "<p>Could not connect to <code>" + escape(url) + "</code></p>"
                + "<div class=\"box\"><ol>"
                + "<li>On your computer (same Wi‑Fi): <code>apex mobile</code></li>"
                + "<li>Copy the printed URL into Settings → Desktop URL</li>"
                + "<li>Or switch Settings to <strong>On this phone</strong> for offline mode</li>"
                + "</ol></div></body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private static String escape(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
