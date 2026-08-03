package io.apex.standalone;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

public class SettingsActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SharedPreferences prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.parseColor("#070b13"));

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);

        TextView headline = new TextView(this);
        headline.setText(R.string.settings_headline);
        headline.setTextColor(Color.parseColor("#63e6ff"));
        headline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        layout.addView(headline);

        TextView explain = new TextView(this);
        explain.setText(R.string.settings_intro);
        explain.setTextColor(Color.parseColor("#b9c8dc"));
        explain.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        explain.setPadding(0, 12, 0, 20);
        layout.addView(explain);

        RadioGroup modes = new RadioGroup(this);
        RadioButton onDevice = new RadioButton(this);
        onDevice.setText(getString(R.string.mode_on_device));
        onDevice.setTextColor(Color.parseColor("#eef4ff"));
        RadioButton remote = new RadioButton(this);
        remote.setText(getString(R.string.mode_remote));
        remote.setTextColor(Color.parseColor("#eef4ff"));
        modes.addView(onDevice);
        modes.addView(remote);
        layout.addView(modes);

        boolean remoteMode = MainActivity.MODE_REMOTE.equals(
                prefs.getString(MainActivity.KEY_MODE, MainActivity.MODE_ON_DEVICE)
        );
        if (remoteMode) {
            remote.setChecked(true);
        } else {
            onDevice.setChecked(true);
        }

        TextView remoteLabel = new TextView(this);
        remoteLabel.setText(R.string.remote_url_label);
        remoteLabel.setTextColor(Color.parseColor("#8fa1bb"));
        remoteLabel.setPadding(0, 16, 0, 8);
        layout.addView(remoteLabel);

        EditText remoteUrl = new EditText(this);
        remoteUrl.setHint(getString(R.string.server_hint));
        remoteUrl.setText(MainActivity.getRemoteUrl(this));
        remoteUrl.setTextColor(Color.parseColor("#eef4ff"));
        remoteUrl.setHintTextColor(Color.parseColor("#4f6688"));
        layout.addView(remoteUrl);

        TextView remoteHelp = new TextView(this);
        remoteHelp.setText(R.string.remote_url_help);
        remoteHelp.setTextColor(Color.parseColor("#8fa1bb"));
        remoteHelp.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        remoteHelp.setPadding(0, 8, 0, 16);
        layout.addView(remoteHelp);

        Button save = new Button(this);
        save.setText(getString(R.string.save));
        save.setOnClickListener(v -> {
            String mode = remote.isChecked() ? MainActivity.MODE_REMOTE : MainActivity.MODE_ON_DEVICE;
            String url = remoteUrl.getText().toString().trim();
            if (remote.isChecked()) {
                if (!url.startsWith("http://") && !url.startsWith("https://")) {
                    Toast.makeText(this, R.string.remote_url_invalid, Toast.LENGTH_SHORT).show();
                    return;
                }
            }
            prefs.edit()
                    .putString(MainActivity.KEY_MODE, mode)
                    .putString(MainActivity.KEY_REMOTE_URL, url)
                    .apply();

            if (MainActivity.MODE_ON_DEVICE.equals(mode)) {
                Intent service = new Intent(this, ApexEngineService.class);
                service.setAction(ApexEngineService.ACTION_START);
                service.putExtra(ApexEngineService.EXTRA_REMOTE_ENHANCED, false);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(service);
                } else {
                    startService(service);
                }
            }

            Toast.makeText(this, R.string.settings_saved, Toast.LENGTH_SHORT).show();
            startActivity(new Intent(this, MainActivity.class));
            finish();
        });
        layout.addView(save);

        scroll.addView(layout);
        setContentView(scroll);
    }
}
