package io.apex.standalone;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.Toast;

public class SettingsActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SharedPreferences prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);

        RadioGroup modes = new RadioGroup(this);
        RadioButton onDevice = new RadioButton(this);
        onDevice.setText(getString(R.string.mode_on_device));
        RadioButton remote = new RadioButton(this);
        remote.setText(getString(R.string.mode_remote));
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

        EditText remoteUrl = new EditText(this);
        remoteUrl.setHint(getString(R.string.server_hint));
        remoteUrl.setText(MainActivity.getRemoteUrl(this));
        layout.addView(remoteUrl);

        Button save = new Button(this);
        save.setText(getString(R.string.save));
        save.setOnClickListener(v -> {
            String mode = remote.isChecked() ? MainActivity.MODE_REMOTE : MainActivity.MODE_ON_DEVICE;
            String url = remoteUrl.getText().toString().trim();
            if (remote.isChecked()) {
                if (!url.startsWith("http://") && !url.startsWith("https://")) {
                    Toast.makeText(this, "URL must start with http:// or https://", Toast.LENGTH_SHORT).show();
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

            Toast.makeText(this, "Saved — reopening APEX", Toast.LENGTH_SHORT).show();
            startActivity(new Intent(this, MainActivity.class));
            finish();
        });
        layout.addView(save);

        setContentView(layout);
    }
}
