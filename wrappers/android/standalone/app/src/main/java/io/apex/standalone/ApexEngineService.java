package io.apex.standalone;

import android.app.ActivityManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import com.chaquo.python.Python;

/**
 * Foreground service that runs the embedded Python APEX engine on localhost.
 */
public class ApexEngineService extends Service {
    public static final String ACTION_START = "io.apex.standalone.START_ENGINE";
    public static final String EXTRA_REMOTE_ENHANCED = "remote_enhanced";
    public static final int PORT = 8765;

    private Thread serverThread;
    private volatile boolean running = false;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        boolean remoteEnhanced = intent != null && intent.getBooleanExtra(EXTRA_REMOTE_ENHANCED, false);
        startForeground(1, buildNotification(getString(R.string.engine_notification_body)));
        if (serverThread == null || !serverThread.isAlive()) {
            running = true;
            serverThread = new Thread(() -> runEngine(remoteEnhanced), "apex-engine");
            serverThread.start();
        }
        return START_STICKY;
    }

    private void runEngine(boolean remoteEnhanced) {
        EngineState.set(EngineState.Phase.STARTING, "Starting analysis engine");
        updateNotification(getString(R.string.engine_notification_starting));
        try {
            ActivityManager am = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
            ActivityManager.MemoryInfo memoryInfo = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(memoryInfo);
            long ramMb = memoryInfo.totalMem / (1024 * 1024);
            int cpuCores = Runtime.getRuntime().availableProcessors();
            String workspace = getFilesDir().getAbsolutePath() + "/apex-workspace";

            EngineState.set(EngineState.Phase.LOADING_PYTHON, "Loading Python modules");
            updateNotification("Loading Python — first launch can take 2–3 minutes");

            Python py = Python.getInstance();
            py.getModule("apex.android_boot").callAttr(
                    "serve_standalone",
                    workspace,
                    PORT,
                    ramMb,
                    cpuCores,
                    remoteEnhanced
            );
            EngineState.set(EngineState.Phase.LISTENING, "Engine listening");
        } catch (Exception e) {
            String message = e.getMessage() == null ? e.toString() : e.getMessage();
            EngineState.fail(message);
            e.printStackTrace();
            updateNotification("Engine failed: " + message);
        } finally {
            running = false;
        }
    }

    private void updateNotification(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.notify(1, buildNotification(text));
    }

    private Notification buildNotification(String body) {
        String channelId = "apex_engine";
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    channelId,
                    getString(R.string.engine_notification_title),
                    NotificationManager.IMPORTANCE_LOW
            );
            nm.createNotificationChannel(channel);
        }
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(
                this,
                0,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, channelId)
                : new Notification.Builder(this);
        return builder
                .setContentTitle(getString(R.string.engine_notification_title))
                .setContentText(body)
                .setSmallIcon(android.R.drawable.sym_def_app_icon)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        running = false;
        if (serverThread != null) {
            serverThread.interrupt();
        }
    }

    public static boolean isEngineRunning() {
        return EngineState.getPhase() == EngineState.Phase.LISTENING
                || EngineState.getPhase() == EngineState.Phase.LOADING_APEX
                || EngineState.getPhase() == EngineState.Phase.LOADING_PYTHON;
    }
}
