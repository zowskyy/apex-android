package io.apex.standalone;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * APEX Mobile — on-device engine by default, optional desktop remote for extra power.
 */
public class MainActivity extends Activity {
    static final String PREFS = "apex_standalone";
    static final String KEY_MODE = "engine_mode";
    static final String KEY_REMOTE_URL = "remote_url";
    static final String MODE_ON_DEVICE = "on_device";
    static final String MODE_REMOTE = "remote";
    static final String LOCAL_URL = "http://127.0.0.1:" + ApexEngineService.PORT;

    private static final int PERM_NOTIFICATIONS = 1001;
    private static final int REQUEST_SELECT_FILE = 1002;
    private static final int MAX_WAIT_ATTEMPTS = 360; // 3 minutes

    private WebView webView;
    private TextView statusText;
    private ProgressBar progressBar;
    private LinearLayout loadingPanel;
    private volatile boolean uiReady = false;
    private ValueCallback<Uri[]> pendingFileCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (!prefs.getBoolean(DisclaimerActivity.KEY_ACCEPTED, false)) {
            startActivity(new Intent(this, DisclaimerActivity.class));
            finish();
            return;
        }

        requestRuntimePermissions();
        buildUi();

        if (isOnDeviceMode(this)) {
            startLocalEngine();
            waitForLocalEngine(LOCAL_URL);
        } else {
            connectRemote(getRemoteUrl(this));
        }
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#070b13"));

        loadingPanel = new LinearLayout(this);
        loadingPanel.setOrientation(LinearLayout.VERTICAL);
        loadingPanel.setGravity(Gravity.CENTER);
        loadingPanel.setPadding(dp(24), dp(32), dp(24), dp(16));

        TextView brand = new TextView(this);
        brand.setText(R.string.app_name);
        brand.setTextColor(Color.parseColor("#63e6ff"));
        brand.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28);
        brand.setGravity(Gravity.CENTER);
        loadingPanel.addView(brand);

        progressBar = new ProgressBar(this);
        LinearLayout.LayoutParams progressLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        progressLp.topMargin = dp(24);
        progressBar.setLayoutParams(progressLp);
        loadingPanel.addView(progressBar);

        statusText = new TextView(this);
        statusText.setTextColor(Color.parseColor("#8fa1bb"));
        statusText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        statusText.setGravity(Gravity.CENTER);
        statusText.setPadding(0, dp(16), 0, 0);
        statusText.setText(getString(R.string.engine_starting));
        loadingPanel.addView(statusText);

        webView = new WebView(this);
        webView.setVisibility(View.GONE);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView view,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params
            ) {
                if (pendingFileCallback != null) {
                    pendingFileCallback.onReceiveValue(null);
                }
                pendingFileCallback = callback;

                Intent intent = params.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(
                            Intent.createChooser(intent, getString(R.string.choose_apk)),
                            REQUEST_SELECT_FILE
                    );
                } catch (ActivityNotFoundException e) {
                    pendingFileCallback = null;
                    return false;
                }
                return true;
            }
        });

        LinearLayout.LayoutParams webLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        webView.setLayoutParams(webLp);

        root.addView(loadingPanel);
        root.addView(webView);
        setContentView(root);
    }

    private void requestRuntimePermissions() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, PERM_NOTIFICATIONS);
            }
        }
    }

    private void startLocalEngine() {
        Intent service = new Intent(this, ApexEngineService.class);
        service.setAction(ApexEngineService.ACTION_START);
        service.putExtra(ApexEngineService.EXTRA_REMOTE_ENHANCED, false);
        startEngineService(service);
    }

    private void startEngineService(Intent service) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(service);
        } else {
            startService(service);
        }
    }

    private void setStatus(String message) {
        if (statusText != null) {
            statusText.setText(message);
        }
    }

    private void showWebUi(String url) {
        uiReady = true;
        loadingPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        webView.loadUrl(url);
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
            for (int attempt = 0; attempt < MAX_WAIT_ATTEMPTS; attempt++) {
                EngineState.Phase phase = EngineState.getPhase();
                if (phase == EngineState.Phase.FAILED) {
                    runOnUiThread(() -> {
                        setStatus(EngineState.getError());
                        EngineHelp.showEngineFailed(webView, EngineState.getError());
                        loadingPanel.setVisibility(View.GONE);
                        webView.setVisibility(View.VISIBLE);
                    });
                    return;
                }
                if (attempt < 5) {
                    postStatus(getString(R.string.engine_starting));
                } else if (attempt < 40) {
                    postStatus(getString(R.string.engine_loading_modules));
                } else {
                    postStatus(getString(R.string.engine_first_launch_hint));
                }
                if (pingHealth(url)) {
                    runOnUiThread(() -> showWebUi(url));
                    return;
                }
                try {
                    Thread.sleep(500);
                } catch (InterruptedException ignored) {
                    break;
                }
            }
            runOnUiThread(() -> {
                setStatus(getString(R.string.engine_timeout));
                EngineHelp.showEngineFailed(webView, getString(R.string.engine_timeout));
                loadingPanel.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            });
        }).start();
    }

    private void postStatus(final String message) {
        runOnUiThread(() -> setStatus(message));
    }

    private void connectRemote(final String url) {
        postStatus(getString(R.string.remote_connecting));
        new Thread(() -> {
            for (int attempt = 0; attempt < 24; attempt++) {
                if (pingHealth(url)) {
                    runOnUiThread(() -> showWebUi(url));
                    return;
                }
                try {
                    Thread.sleep(500);
                } catch (InterruptedException ignored) {
                    break;
                }
            }
            runOnUiThread(() -> {
                loadingPanel.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
                EngineHelp.showRemoteFailed(webView, url);
            });
        }).start();
    }

    private boolean pingHealth(String baseUrl) {
        try {
            URL health = new URL(baseUrl + "/api/health");
            HttpURLConnection conn = (HttpURLConnection) health.openConnection();
            conn.setConnectTimeout(2500);
            conn.setReadTimeout(2500);
            conn.connect();
            return conn.getResponseCode() == 200;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQUEST_SELECT_FILE) {
            if (pendingFileCallback != null) {
                Uri[] results = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
                pendingFileCallback.onReceiveValue(results);
                pendingFileCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
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
        if (webView == null || !uiReady) {
            return;
        }
        if (isOnDeviceMode(this)) {
            if (pingHealth(LOCAL_URL)) {
                webView.loadUrl(LOCAL_URL);
            }
        } else {
            String url = getRemoteUrl(this);
            if (pingHealth(url)) {
                webView.loadUrl(url);
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.getVisibility() == View.VISIBLE && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
