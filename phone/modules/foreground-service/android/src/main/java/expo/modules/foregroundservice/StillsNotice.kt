package expo.modules.foregroundservice

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat

object StillsNotice {
  private const val CHANNEL_ID = "stills_arriving"
  private const val NOTIFICATION_ID = 0xB3C2
  private const val ACTIVE_TIMEOUT_MS = 60_000L

  fun show(context: Context, title: String, body: String, got: Int, size: Int, active: Boolean) {
    val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    manager.createNotificationChannel(
      NotificationChannel(CHANNEL_ID, "Stills arriving", NotificationManager.IMPORTANCE_DEFAULT).apply {
        description = "Progress while stills arrive from the camera, and what arrived."
        setSound(null, null)
        enableVibration(false)
        setShowBadge(false)
      },
    )
    val open = PendingIntent.getActivity(
      context,
      1,
      Intent(Intent.ACTION_VIEW, Uri.parse("bendcam://stills")).setPackage(context.packageName),
      PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
    val builder = NotificationCompat.Builder(context, CHANNEL_ID)
      .setContentTitle(title)
      .setContentText(body)
      .setStyle(NotificationCompat.BigTextStyle().bigText(body))
      .setSmallIcon(if (active) android.R.drawable.stat_sys_download else android.R.drawable.stat_sys_download_done)
      .setOngoing(active)
      .setAutoCancel(!active)
      .setSilent(true)
      .setOnlyAlertOnce(true)
      .setCategory(NotificationCompat.CATEGORY_PROGRESS)
      .setContentIntent(open)
    if (size > 0) builder.setProgress(size, got.coerceIn(0, size), false)
    if (active) builder.setTimeoutAfter(ACTIVE_TIMEOUT_MS)
    manager.notify(NOTIFICATION_ID, builder.build())
  }

  fun clear(context: Context) {
    val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    manager.cancel(NOTIFICATION_ID)
  }
}
