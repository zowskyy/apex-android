package io.apex.standalone;

import android.app.Application;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class ApexApplication extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        EngineState.set(EngineState.Phase.IDLE, "APEX ready to start");
        if (!Python.isStarted()) {
            try {
                Python.start(new AndroidPlatform(this));
            } catch (Exception e) {
                EngineState.fail("Python runtime failed: " + e.getMessage());
            }
        }
    }
}
