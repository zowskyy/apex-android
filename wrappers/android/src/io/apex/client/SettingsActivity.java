package io.apex.client;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.util.TypedValue;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class SettingsActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);
        layout.setBackgroundColor(Color.parseColor("#070b13"));

        TextView headline = new TextView(this);
        headline.setText(R.string.companion_settings_headline);
        headline.setTextColor(Color.parseColor("#63e6ff"));
        headline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        layout.addView(headline);

        TextView explain = new TextView(this);
        explain.setText(R.string.companion_settings_body);
        explain.setTextColor(Color.parseColor("#b9c8dc"));
        explain.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        explain.setPadding(0, 12, 0, 16);
        layout.addView(explain);

        EditText input = new EditText(this);
        input.setHint(getString(R.string.server_hint));
        input.setText(MainActivity.getServerUrl(this));
        input.setTextColor(Color.parseColor("#eef4ff"));
        layout.addView(input);

        Button save = new Button(this);
        save.setText(getString(R.string.save));
        save.setOnClickListener(v -> {
            String url = input.getText().toString().trim();
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                Toast.makeText(this, "URL must start with http:// or https://", Toast.LENGTH_SHORT).show();
                return;
            }
            SharedPreferences prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);
            prefs.edit().putString(MainActivity.KEY_URL, url).apply();
            Toast.makeText(this, "Saved — reconnecting", Toast.LENGTH_SHORT).show();
            finish();
        });
        layout.addView(save);

        setContentView(layout);
    }
}
