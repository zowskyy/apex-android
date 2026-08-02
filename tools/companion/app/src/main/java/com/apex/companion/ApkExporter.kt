package com.apex.companion

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File

/**
 * Exports a selected app's APK set to shared storage so the user can move it to
 * the APEX desktop workstation for full analysis.
 *
 * Export is always user-initiated for a specific app. Nothing is collected in
 * the background and the app declares no network permission.
 */
object ApkExporter {

    data class ExportedArtifact(
        val name: String,
        val sha256: String?,
        val bytes: Long,
        val location: String,
    )

    fun export(context: Context, app: DeviceApp): List<ExportedArtifact> {
        val exported = mutableListOf<ExportedArtifact>()
        app.apkPaths.forEachIndexed { index, path ->
            val source = File(path)
            if (!source.isFile) return@forEachIndexed
            val name = if (index == 0) {
                "${app.packageName}-${app.versionCode}-base.apk"
            } else {
                "${app.packageName}-${app.versionCode}-split$index.apk"
            }
            val location = writeToDownloads(context, source, name) ?: return@forEachIndexed
            exported += ExportedArtifact(
                name = name,
                sha256 = AppInventory.sha256(path),
                bytes = source.length(),
                location = location,
            )
        }
        return exported
    }

    private fun writeToDownloads(context: Context, source: File, name: String): String? = try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, "application/vnd.android.package-archive")
                put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/APEX")
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            if (uri == null) {
                null
            } else {
                resolver.openOutputStream(uri)?.use { output ->
                    source.inputStream().use { input -> input.copyTo(output) }
                }
                values.clear()
                values.put(MediaStore.Downloads.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
                uri.toString()
            }
        } else {
            @Suppress("DEPRECATION")
            val directory = File(
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
                "APEX",
            )
            directory.mkdirs()
            val target = File(directory, name)
            source.inputStream().use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            }
            target.absolutePath
        }
    } catch (_: Exception) {
        null
    }
}
