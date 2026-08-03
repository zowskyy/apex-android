package io.apex.standalone;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Full-stack APEX on the phone: embedded engine by default, optional remote desktop backend.
 */
public class MainActivity extends Activity {
    static final String PREFS = "apex_standalone";
    static final String KEY_MODE = "engine_mode";
    static final String KEY_REMOTE_URL = "remote_url";
    static final String MODE_ON_DEVICE = "on_device";
    static final String MODE_REMOTE = "remote";
    static final String LOCAL_URL = "http://127.0.0.1:" + ApexEngineService.PORT;

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

        if (isOnDeviceMode(this)) {
            Toast.makeText(this, R.string.engine_starting, Toast.LENGTH_SHORT).show();
            Intent service = new Intent(this, ApexEngineService.class);
            service.setAction(ApexEngineService.ACTION_START);
            service.putExtra(ApexEngineService.EXTRA_REMOTE_ENHANCED, false);
            startEngineService(service);
            waitForLocalEngine(LOCAL_URL);
        } else {
            connectRemote(getRemoteUrl(this));
        }
    }

    private void connectRemote(final String url) {
        new Thread(() -> {
            final boolean ok = pingHealth(url);
            runOnUiThread(() -> {
                if (ok) {
                    webView.loadUrl(url);
                } else {
                    EngineHelp.showRemoteFailed(webView, url);
                }
            });
        }).start();
    }

    private void startEngineService(Intent service) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(service);
        } else {
            startService(service);
        }
    }

    static boolean isOnDeviceMode(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, MODE_PRIVATE);
        return MODE_ON_DEVICE.equals(prefs.getString(KEY_MODE, MODE_ON_DEVICE));
    }

    static String getRemoteUrl(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, MODE_PRIVATE);
        return prefs.getString(KEY_REMOTE_URL, "http://192.168.1.42:8765");
    }

    private void waitForLocalEngine(final String url) {
        new Thread(() -> {
            boolean ready = false;
            for (int attempt = 0; attempt < 120; attempt++) {
                if (pingHealth(url)) {
                    ready = true;
                    break;
                }
                try {
                    Thread.sleep(500);
                } catch (InterruptedException ignored) {
                    break;
                }
            }
            final boolean ok = ready;
            runOnUiThread(() -> {
                if (ok) {
                    webView.loadUrl(url);
                } else {
                    EngineHelp.showEngineFailed(webView);
                }
            });
        }).start();
    }

    private boolean pingHealth(String baseUrl) {
        try {
            URL health = new URL(baseUrl + "/api/health");
            HttpURLConnection conn = (HttpURLConnection) health.openConnection();
            conn.setConnectTimeout(800);
            conn.setReadTimeout(800);
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
        if (isOnDeviceMode(this)) {
            webView.loadUrl(LOCAL_URL);
        } else {
            webView.loadUrl(getRemoteUrl(this));
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
