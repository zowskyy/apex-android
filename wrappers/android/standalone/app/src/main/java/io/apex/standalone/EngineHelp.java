package io.apex.standalone;

import android.webkit.WebView;

final class EngineHelp {
    private EngineHelp() {}

    static void showEngineFailed(WebView webView) {
        String html =
                "<!doctype html><html><head><meta charset=utf-8>"
                + "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "body{margin:0;padding:24px;background:#070b13;color:#eef4ff;font:15px/1.5 sans-serif}"
                + "h1{color:#63e6ff;font-size:22px}"
                + ".box{border:1px solid #263651;border-radius:12px;padding:16px;margin:16px 0;background:#0e1625;color:#b9c8dc}"
                + "</style></head><body>"
                + "<h1>On-device engine did not start</h1>"
                + "<div class=\"box\"><p>Try: force-stop the app, reopen, and wait 30–60 seconds.</p>"
                + "<p>If this persists, reinstall <code>apex-mobile.apk</code> from "
                + "GitHub Actions → <strong>Android standalone APK</strong> (not apex-client-apk).</p>"
                + "<p>Menu → Settings → Desktop server if you want to use a PC instead.</p></div>"
                + "</body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    static void showRemoteFailed(WebView webView, String url) {
        String html =
                "<!doctype html><html><head><meta charset=utf-8>"
                + "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "body{margin:0;padding:24px;background:#070b13;color:#eef4ff;font:15px/1.5 sans-serif}"
                + "h1{color:#63e6ff;font-size:22px}"
                + "p{color:#b9c8dc}"
                + "code{background:#131e30;padding:2px 6px}"
                + "</style></head><body>"
                + "<h1>Desktop server not reachable</h1>"
                + "<p>Could not connect to <code>" + escape(url) + "</code></p>"
                + "<p>Run <code>apex mobile</code> on your PC (same Wi‑Fi) or switch Settings to "
                + "<strong>On-device engine</strong>.</p></body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private static String escape(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
