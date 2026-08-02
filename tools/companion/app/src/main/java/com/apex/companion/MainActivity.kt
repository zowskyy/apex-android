package com.apex.companion

import android.os.Bundle
import android.text.format.DateFormat
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class MainActivity : AppCompatActivity() {

    private lateinit var adapter: AppAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val list = findViewById<RecyclerView>(R.id.appList)
        val summary = findViewById<TextView>(R.id.summary)

        adapter = AppAdapter(::showDetail)
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter

        val apps = AppInventory.launchableApps(this)
        adapter.submit(apps)
        summary.text = getString(R.string.summary_format, apps.size)
    }

    private fun showDetail(app: DeviceApp) {
        val installed = DateFormat.getDateFormat(this).format(app.firstInstallTime)
        val updated = DateFormat.getDateFormat(this).format(app.lastUpdateTime)
        val details = buildString {
            appendLine("Package: ${app.packageName}")
            appendLine("Version: ${app.versionName} (${app.versionCode})")
            appendLine("Type: ${if (app.isSystem) "system" else "user"}")
            appendLine("Installed: $installed")
            appendLine("Updated: $updated")
            appendLine("Splits: ${app.splitCount}")
            appendLine()
            appendLine("APK paths:")
            app.apkPaths.forEach { appendLine("  $it") }
        }

        AlertDialog.Builder(this)
            .setTitle(app.label)
            .setMessage(details)
            .setPositiveButton(R.string.export) { _, _ -> exportApp(app) }
            .setNegativeButton(R.string.close, null)
            .show()
    }

    private fun exportApp(app: DeviceApp) {
        val exported = ApkExporter.export(this, app)
        val message = if (exported.isEmpty()) {
            getString(R.string.export_failed)
        } else {
            getString(R.string.export_done, exported.size)
        }
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }
}

private class AppAdapter(
    private val onClick: (DeviceApp) -> Unit,
) : RecyclerView.Adapter<AppAdapter.Holder>() {

    private val items = mutableListOf<DeviceApp>()

    fun submit(apps: List<DeviceApp>) {
        items.clear()
        items.addAll(apps)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_app, parent, false)
        return Holder(view)
    }

    override fun onBindViewHolder(holder: Holder, position: Int) {
        holder.bind(items[position], onClick)
    }

    override fun getItemCount(): Int = items.size

    class Holder(view: View) : RecyclerView.ViewHolder(view) {
        private val title = view.findViewById<TextView>(R.id.appLabel)
        private val subtitle = view.findViewById<TextView>(R.id.appPackage)

        fun bind(app: DeviceApp, onClick: (DeviceApp) -> Unit) {
            title.text = app.label
            subtitle.text = "${app.packageName} · ${app.versionName}"
            itemView.setOnClickListener { onClick(app) }
        }
    }
}
