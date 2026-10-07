package expo.modules.foregroundservice

import android.content.Intent
import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.ReactContext
import com.facebook.react.bridge.UiThreadUtil
import com.facebook.react.jstasks.HeadlessJsTaskConfig
import com.facebook.react.jstasks.HeadlessJsTaskContext
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class ForegroundServiceModule : Module() {
  private var task: Int? = null

  override fun definition() = ModuleDefinition {
    Name("ForegroundService")

    AsyncFunction("start") { title: String, body: String ->
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      val intent = Intent(context, TransferService::class.java).apply {
        putExtra(TransferService.EXTRA_TITLE, title)
        putExtra(TransferService.EXTRA_BODY, body)
      }
      TransferService.markStarting()
      context.startForegroundService(intent)
      holdTimers()
      Unit
    }

    AsyncFunction("update") { title: String, body: String ->
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      TransferService.update(context, title, body)
    }

    AsyncFunction("stop") {
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      releaseTimers()
      if (TransferService.requestStop()) {
        context.stopService(Intent(context, TransferService::class.java))
      }
    }

    AsyncFunction("stills") { title: String, body: String, got: Int, size: Int, active: Boolean ->
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      StillsNotice.show(context, title, body, got, size, active)
    }

    AsyncFunction("clearStills") {
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      StillsNotice.clear(context)
    }

    AsyncFunction("isRunning") {
      TransferService.isRunning
    }
  }

  private fun holdTimers() {
    val react = appContext.reactContext as? ReactContext ?: return
    UiThreadUtil.runOnUiThread {
      if (task != null) return@runOnUiThread
      task = HeadlessJsTaskContext.getInstance(react).startTask(
        HeadlessJsTaskConfig(TASK, Arguments.createMap(), 0, true),
      )
    }
  }

  private fun releaseTimers() {
    val react = appContext.reactContext as? ReactContext ?: return
    UiThreadUtil.runOnUiThread {
      task?.let { HeadlessJsTaskContext.getInstance(react).finishTask(it) }
      task = null
    }
  }

  companion object {
    const val TASK = "BendcamKeepAlive"
  }
}
