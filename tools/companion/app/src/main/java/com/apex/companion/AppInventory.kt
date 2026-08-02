package com.apex.companion

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import java.io.File
import java.security.MessageDigest

/**
 * Launchable-app inventory using the narrow package-visibility model.
 *
 * This intentionally avoids QUERY_ALL_PACKAGES. Apps discoverable through the
 * launcher intent are the ones a user actually interacts with, which covers the
 * companion's purpose without requesting sensitive broad inventory access.
 */
data class DeviceApp(
    val packageName: String,
    val label: String,
    val versionName: String,
    val versionCode: Long,
    val isSystem: Boolean,
    val firstInstallTime: Long,
    val lastUpdateTime: Long,
    val apkPaths: List<String>,
) {
    val splitCount: Int get() = (apkPaths.size - 1).coerceAtLeast(0)
}

object AppInventory {

    fun launchableApps(context: Context): List<DeviceApp> {
        val packageManager = context.packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val resolved = packageManager.queryIntentActivities(intent, 0)

        return resolved
            .map { it.activityInfo.packageName }
            .distinct()
            .mapNotNull { packageName -> describe(context, packageName) }
            .sortedBy { it.label.lowercase() }
    }

    fun describe(context: Context, packageName: String): DeviceApp? {
        val packageManager = context.packageManager
        return try {
            val info = packageManager.getPackageInfo(packageName, 0)
            val appInfo = info.applicationInfo ?: return null
            val paths = buildList {
                appInfo.sourceDir?.let { add(it) }
                appInfo.splitSourceDirs?.forEach { add(it) }
            }
            DeviceApp(
                packageName = packageName,
                label = packageManager.getApplicationLabel(appInfo).toString(),
                versionName = info.versionName ?: "unknown",
                versionCode = versionCodeOf(info),
                isSystem = (appInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0,
                firstInstallTime = info.firstInstallTime,
                lastUpdateTime = info.lastUpdateTime,
                apkPaths = paths,
            )
        } catch (_: PackageManager.NameNotFoundException) {
            null
        }
    }

    @Suppress("DEPRECATION")
    private fun versionCodeOf(info: android.content.pm.PackageInfo): Long =
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            info.longVersionCode
        } else {
            info.versionCode.toLong()
        }

    /**
     * SHA-256 of an APK artifact so the desktop workstation can confirm it
     * analyzed exactly the bytes the device held.
     */
    fun sha256(path: String): String? = try {
        val digest = MessageDigest.getInstance("SHA-256")
        File(path).inputStream().use { stream ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val read = stream.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        digest.digest().joinToString(":") { "%02x".format(it) }
    } catch (_: Exception) {
        null
    }
}
