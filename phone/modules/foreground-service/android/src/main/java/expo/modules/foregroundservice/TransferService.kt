package expo.modules.foregroundservice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat

class TransferService : Service() {

  companion object {
    const val EXTRA_TITLE = "title"
    const val EXTRA_BODY = "body"

    private const val CHANNEL_ID = "stills_transfer"
    private const val NOTIFICATION_ID = 0xB3C1

    @Volatile
    var isRunning: Boolean = false
      private set

    private val stateLock = Any()
    private var stopRequested: Boolean = false

    fun markStarting() = synchronized(stateLock) { stopRequested = false }

    fun requestStop(): Boolean = synchronized(stateLock) {
      if (isRunning) return@synchronized true
      stopRequested = true
      false
    }

    private fun markStartedAndConsumeStop(): Boolean = synchronized(stateLock) {
      isRunning = true
      val requested = stopRequested
      stopRequested = false
      requested
    }

    fun update(context: Context, title: String, body: String) {
      if (!isRunning) return
      val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
      manager.notify(NOTIFICATION_ID, build(context, title, body))
    }

    private fun build(context: Context, title: String, body: String): Notification {
      val launch = context.packageManager.getLaunchIntentForPackage(context.packageName)
      val pending = launch?.let {
        PendingIntent.getActivity(
          context, 0, it, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
      }
      return NotificationCompat.Builder(context, CHANNEL_ID)
        .setContentTitle(title)
        .setContentText(body)
        .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
        .setOngoing(true)
        .setSilent(true)
        .setOnlyAlertOnce(true)
        .setPriority(NotificationCompat.PRIORITY_LOW)
        .setContentIntent(pending)
        .build()
    }
  }

  override fun onBind(intent: Intent?): IBinder? = null

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    val title = intent?.getStringExtra(EXTRA_TITLE) ?: "bendcam"
    val body = intent?.getStringExtra(EXTRA_BODY) ?: ""

    val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    manager.createNotificationChannel(
      NotificationChannel(CHANNEL_ID, "Camera link", NotificationManager.IMPORTANCE_LOW).apply {
        description = "Shown while the app keeps its link to the camera."
        setShowBadge(false)
      },
    )

    ServiceCompat.startForeground(
      this,
      NOTIFICATION_ID,
      build(this, title, body),
      ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE,
    )

    if (markStartedAndConsumeStop()) {
      ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
      stopSelf(startId)
    }
    return START_NOT_STICKY
  }

  override fun onDestroy() {
    synchronized(stateLock) { isRunning = false }
    super.onDestroy()
  }
}
