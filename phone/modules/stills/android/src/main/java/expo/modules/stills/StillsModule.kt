package expo.modules.stills

import android.content.ContentValues
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.typedarray.Uint8Array
import java.io.File
import java.io.FileOutputStream

class StillsModule : Module() {

  override fun definition() = ModuleDefinition {
    Name("Stills")

    Function("dir") {
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      val dir = context.getExternalFilesDir("stills") ?: File(context.filesDir, "stills")
      dir.mkdirs()
      Uri.fromFile(dir).toString()
    }

    Function("list") { uri: String ->
      File(path(uri)).list()?.toList() ?: emptyList()
    }

    Function("save") { uri: String, bytes: Uint8Array ->
      FileOutputStream(path(uri)).channel.use { it.write(bytes.toDirectBuffer()) }
      Unit
    }

    AsyncFunction("toJpeg") { bmp: String, jpg: String, quality: Int ->
      val bitmap = BitmapFactory.decodeFile(path(bmp))
        ?: throw CodedException("ERR_DECODE", "Android can't decode ${path(bmp)}", null)
      try {
        File(path(jpg)).outputStream().use { out ->
          if (!bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out)) {
            throw CodedException("ERR_ENCODE", "JPEG encode failed", null)
          }
        }
      } finally {
        bitmap.recycle()
      }
    }

    AsyncFunction("toGallery") { jpg: String, album: String ->
      val context = appContext.reactContext ?: throw Exceptions.ReactContextLost()
      val resolver = context.contentResolver
      val src = File(path(jpg))
      val collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
      val relative = "${Environment.DIRECTORY_PICTURES}/$album/"

      val existing = resolver.query(
        collection,
        arrayOf(MediaStore.Images.Media._ID),
        "${MediaStore.Images.Media.DISPLAY_NAME} = ? AND ${MediaStore.Images.Media.RELATIVE_PATH} = ?",
        arrayOf(src.name, relative),
        null,
      )?.use { c -> if (c.moveToFirst()) Uri.withAppendedPath(collection, c.getLong(0).toString()) else null }

      val uri = existing ?: resolver.insert(
        collection,
        ContentValues().apply {
          put(MediaStore.Images.Media.DISPLAY_NAME, src.name)
          put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
          put(MediaStore.Images.Media.RELATIVE_PATH, relative)
          put(MediaStore.Images.Media.IS_PENDING, 1)
        },
      ) ?: throw CodedException("ERR_GALLERY", "MediaStore refused ${src.name}", null)

      resolver.openOutputStream(uri, "wt")?.use { out -> src.inputStream().use { it.copyTo(out) } }
        ?: throw CodedException("ERR_GALLERY", "Can't write ${src.name} to the gallery", null)
      if (existing == null) {
        resolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
      }
      uri.toString()
    }
  }

  private fun path(uriOrPath: String): String =
    if (uriOrPath.startsWith("file://")) Uri.parse(uriOrPath).path!! else uriOrPath
}
