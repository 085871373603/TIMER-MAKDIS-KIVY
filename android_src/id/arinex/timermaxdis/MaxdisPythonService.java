package id.arinex.timermaxdis;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Notification;
import android.content.Context;
import android.os.Build;
import android.os.Bundle;

import org.kivy.android.PythonService;

/**
 * Keeps python-for-android's foreground notification visible in the drawer.
 * Upstream PythonService currently creates its channel with IMPORTANCE_NONE;
 * create the same channel first with LOW importance, then let the base class
 * build its normal notification against that channel.
 */
public class MaxdisPythonService extends PythonService {
    @Override
    protected void doStartForeground(Bundle extras) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            String channelId = "org.kivy.p4a" + getServiceId();
            NotificationManager manager =
                    (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                NotificationChannel channel = new NotificationChannel(
                        channelId,
                        "TIMER MAXDIS - Status berjalan",
                        NotificationManager.IMPORTANCE_LOW
                );
                channel.setDescription("Menampilkan status TIMER MAXDIS saat hitung mundur berjalan di latar belakang.");
                channel.setShowBadge(false);
                channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
                manager.createNotificationChannel(channel);
            }
        }
        super.doStartForeground(extras);
    }
}
