package io.apex.client;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Thin WebView shell — connects to a PC running {@code apex mobile}.
 * For full on-device analysis use APEX Mobile (apex-mobile.apk).
 */
public class MainActivity extends Activity {
    static final String PREFS = "apex_client";
    static final String KEY_URL = "server_url";
    static final String DEFAULT_URL = "http://192.168.1.1:8765";

    private WebView webView;
    private String lastLoadedUrl = "";
    private boolean showingHelp = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (!prefs.getBoolean(DisclaimerActivity.KEY_ACCEPTED, false)) {
            startActivity(new Intent(this, DisclaimerActivity.class));
            finish();
            return;
        }

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    showingHelp = true;
                    CompanionHelp.show(view, getServerUrl(MainActivity.this));
                }
            }

            @Override
            @SuppressWarnings("deprecation")
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                showingHelp = true;
                CompanionHelp.show(view, failingUrl);
            }
        });

        connectOrShowHelp(getServerUrl(this));
    }

    private void connectOrShowHelp(final String url) {
        showingHelp = false;
        lastLoadedUrl = url;
        webView.loadDataWithBaseURL(
                null,
                "<html><body style=\"background:#070b13;color:#8fa1bb;text-align:center;padding:48px\">"
                        + "Connecting to APEX server…</body></html>",
                "text/html",
                "UTF-8",
                null
        );
        new Thread(() -> {
            final boolean ok = pingHealth(url);
            runOnUiThread(() -> {
                if (ok) {
                    showingHelp = false;
                    webView.loadUrl(url);
                } else {
                    showingHelp = true;
                    CompanionHelp.show(webView, url);
                }
            });
        }).start();
    }

    private boolean pingHealth(String baseUrl) {
        try {
            URL health = new URL(baseUrl + "/api/health");
            HttpURLConnection conn = (HttpURLConnection) health.openConnection();
            conn.setConnectTimeout(2000);
            conn.setReadTimeout(2000);
            conn.connect();
            if (conn.getResponseCode() != 200) {
                return false;
            }
            BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
            String line = reader.readLine();
            reader.close();
            return line != null && line.contains("ready");
        } catch (Exception e) {
            return false;
        }
    }

    static String getServerUrl(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, MODE_PRIVATE);
        return prefs.getString(KEY_URL, DEFAULT_URL);
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, getString(R.string.open_settings));
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView == null) {
            return;
        }
        String url = getServerUrl(this);
        if (!url.equals(lastLoadedUrl) || showingHelp) {
            connectOrShowHelp(url);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack() && !showingHelp) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
