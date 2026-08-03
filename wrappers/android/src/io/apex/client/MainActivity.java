package io.apex.client;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    static final String PREFS = "apex_client";
    static final String KEY_URL = "server_url";
    static final String DEFAULT_URL = "http://192.168.1.1:8765";

    private WebView webView;

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

        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl(getServerUrl(this));
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
        if (webView != null) {
            webView.loadUrl(getServerUrl(this));
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
