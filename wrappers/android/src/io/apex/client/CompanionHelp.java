package io.apex.client;

import android.webkit.WebView;

/**
 * Shown when the companion client cannot reach a desktop APEX server.
 */
final class CompanionHelp {
    private CompanionHelp() {}

    static void show(WebView webView, String attemptedUrl) {
        String html =
                "<!doctype html><html><head><meta charset=utf-8>"
                + "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "body{margin:0;padding:24px;background:#070b13;color:#eef4ff;font:15px/1.5 sans-serif}"
                + "h1{color:#63e6ff;font-size:22px;margin:0 0 12px}"
                + "h2{color:#8fa1bb;font-size:14px;margin:24px 0 8px}"
                + "p,li{color:#b9c8dc}"
                + ".box{border:1px solid #263651;border-radius:12px;padding:16px;margin:16px 0;background:#0e1625}"
                + ".warn{border-color:#ff7285;color:#ff7285}"
                + "code{background:#131e30;padding:2px 6px;border-radius:4px}"
                + "ol{padding-left:20px}"
                + "</style></head><body>"
                + "<h1>Companion mode — no server found</h1>"
                + "<div class=\"box warn\"><strong>This APK is not the full on-phone engine.</strong>"
                + " App name: <strong>APEX Companion</strong>. Menu: <strong>Server URL</strong>."
                + " It only displays a PC that is already running APEX.</div>"
                + "<p>Could not connect to:<br><code>" + escape(attemptedUrl) + "</code></p>"
                + "<h2>Option A — Use on-device (no PC)</h2>"
                + "<div class=\"box\"><p>Install <strong>APEX Mobile</strong> instead:</p>"
                + "<ol>"
                + "<li>GitHub → Actions → <strong>Android standalone APK</strong></li>"
                + "<li>Download artifact <strong>apex-mobile-apk</strong></li>"
                + "<li>Install <code>apex-mobile.apk</code> (app name: APEX Mobile)</li>"
                + "</ol>"
                + "<p>Or build: <code>bash build_standalone.sh</code></p></div>"
                + "<h2>Option B — Keep companion + PC</h2>"
                + "<div class=\"box\"><ol>"
                + "<li>On your computer (same Wi‑Fi): <code>apex mobile</code></li>"
                + "<li>Note the URL, e.g. <code>http://192.168.1.42:8765</code></li>"
                + "<li>Menu → <strong>Server URL</strong> → paste that address → Save</li>"
                + "</ol></div>"
                + "<p style=\"color:#8fa1bb;font-size:13px\">Analysis always runs on the machine hosting the server — "
                + "companion phone or PC browser, not inside this thin client by itself.</p>"
                + "</body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private static String escape(String raw) {
        if (raw == null) {
            return "";
        }
        return raw
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;");
    }
}
