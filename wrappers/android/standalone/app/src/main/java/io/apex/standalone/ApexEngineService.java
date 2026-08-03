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
import com.chaquo.python.android.AndroidPlatform;

/**
 * Foreground service that runs the embedded Python APEX engine on localhost.
 */
public class ApexEngineService extends Service {
    public static final String ACTION_START = "io.apex.standalone.START_ENGINE";
    public static final String EXTRA_REMOTE_ENHANCED = "remote_enhanced";
    public static final int PORT = 8765;

    private Thread serverThread;

    @Override
    public void onCreate() {
        super.onCreate();
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        boolean remoteEnhanced = intent != null && intent.getBooleanExtra(EXTRA_REMOTE_ENHANCED, false);
        startForeground(1, buildNotification());
        if (serverThread == null || !serverThread.isAlive()) {
            serverThread = new Thread(() -> runEngine(remoteEnhanced), "apex-engine");
            serverThread.start();
        }
        return START_STICKY;
    }

    private void runEngine(boolean remoteEnhanced) {
        try {
            ActivityManager am = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
            ActivityManager.MemoryInfo memoryInfo = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(memoryInfo);
            long ramMb = memoryInfo.totalMem / (1024 * 1024);
            int cpuCores = Runtime.getRuntime().availableProcessors();
            String workspace = getFilesDir().getAbsolutePath() + "/apex-workspace";

            Python py = Python.getInstance();
            py.getModule("apex.android_boot").callAttr(
                    "serve_standalone",
                    workspace,
                    PORT,
                    ramMb,
                    cpuCores,
                    remoteEnhanced
            );
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private Notification buildNotification() {
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
                .setContentText(getString(R.string.engine_notification_body))
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
        if (serverThread != null) {
            serverThread.interrupt();
        }
    }
}
