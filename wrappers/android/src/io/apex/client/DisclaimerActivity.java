package io.apex.client;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/**
 * First-launch gate: science / education spirit, user liability for harmful misuse.
 */
public class DisclaimerActivity extends Activity {
    static final String KEY_ACCEPTED = "disclaimer_accepted_v1";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SharedPreferences prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);
        if (prefs.getBoolean(KEY_ACCEPTED, false)) {
            openMain();
            return;
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#070b13"));
        root.setPadding(dp(20), dp(28), dp(20), dp(24));

        TextView title = new TextView(this);
        title.setText(R.string.disclaimer_title);
        title.setTextColor(Color.parseColor("#63e6ff"));
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        title.setPadding(0, 0, 0, dp(12));
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText(R.string.disclaimer_subtitle);
        subtitle.setTextColor(Color.parseColor("#8fa1bb"));
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        subtitle.setPadding(0, 0, 0, dp(16));
        root.addView(subtitle);

        ScrollView scroll = new ScrollView(this);
        LinearLayout.LayoutParams scrollLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        scroll.setLayoutParams(scrollLp);

        TextView body = new TextView(this);
        body.setText(R.string.disclaimer_body);
        body.setTextColor(Color.parseColor("#eef4ff"));
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        body.setLineSpacing(dp(4), 1f);
        scroll.addView(body);
        root.addView(scroll);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.VERTICAL);
        buttons.setPadding(0, dp(16), 0, 0);

        Button agree = new Button(this);
        agree.setText(R.string.disclaimer_agree);
        agree.setOnClickListener(v -> {
            prefs.edit().putBoolean(KEY_ACCEPTED, true).apply();
            openMain();
        });
        buttons.addView(agree);

        Button decline = new Button(this);
        decline.setText(R.string.disclaimer_decline);
        decline.setOnClickListener(v -> {
            Toast.makeText(this, R.string.disclaimer_declined, Toast.LENGTH_LONG).show();
            finishAffinity();
        });
        buttons.addView(decline);

        TextView legal = new TextView(this);
        legal.setText(R.string.disclaimer_footer);
        legal.setTextColor(Color.parseColor("#8fa1bb"));
        legal.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        legal.setGravity(Gravity.CENTER);
        legal.setPadding(0, dp(12), 0, 0);
        buttons.addView(legal);

        root.addView(buttons);
        setContentView(root);
    }

    private void openMain() {
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
