"""Dependency-free local web interface for APEX."""

from __future__ import annotations

import json
import re
import tempfile
import threading
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from apex.corpus.stats import corpus_packages, corpus_stats
from apex.device.adb import list_packages
from apex.device.sync import list_connected, sync_device
from apex.intel.detect import detect_android, summarize_detections
from apex.intel.privacy_posture import assess_posture
from apex.providers.registry import get_adb_command
from apex.signing.display import format_signing_panel
from apex.signing.native import analyze_signatures, cross_check_with_apksigner
from apex.version import __version__

from .analysis import ApexError, dex_metadata, inspect_apk, sanitized_zip_name
from .workflows import decompile_apk, doctor, generate_sbom, security_scan

WEB_APP = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>APEX · Android Package EXaminer</title>
<style>
:root{color-scheme:dark;--bg:#070b13;--surface:#0e1625;--surface2:#131e30;--line:#263651;--text:#eef4ff;--muted:#8fa1bb;--cyan:#63e6ff;--violet:#8b7cff;--green:#68e69a;--red:#ff7285}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 75% -10%,#172a4a 0,transparent 42%),var(--bg);color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui}
header{height:68px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 28px;gap:14px;background:#080d17cc;backdrop-filter:blur(14px);position:sticky;top:0;z-index:2}
.mark{width:34px;height:34px;border:1px solid #69e8ff66;border-radius:9px;display:grid;place-items:center;background:linear-gradient(135deg,#5fe8ff22,#8f75ff33);font-weight:900;color:var(--cyan)}
.brand{font-weight:800;letter-spacing:.13em}.tag{color:var(--muted);font-size:12px}.spacer{flex:1}.status{color:var(--green);font-size:12px}
main{max-width:1240px;margin:auto;padding:42px 28px}.hero{display:grid;grid-template-columns:1.25fr .75fr;gap:28px;align-items:center;margin-bottom:34px}
h1{font-size:clamp(35px,5vw,62px);line-height:1.02;letter-spacing:-.045em;margin:0 0 18px}.gradient{background:linear-gradient(90deg,var(--cyan),#b3a8ff);-webkit-background-clip:text;color:transparent}
.lead{font-size:17px;color:var(--muted);max-width:650px}.drop{border:1px dashed #4f6688;border-radius:18px;min-height:210px;padding:28px;display:grid;place-items:center;text-align:center;background:linear-gradient(145deg,#111d30aa,#0b1321)}
.drop.drag{border-color:var(--cyan);box-shadow:0 0 40px #63e6ff14}.drop strong{display:block;font-size:18px}.drop p{color:var(--muted);margin:8px 0 17px}
button,.button{border:0;border-radius:9px;padding:10px 15px;background:linear-gradient(90deg,#27bfdc,#7866e8);color:white;font-weight:700;cursor:pointer}.secondary{background:var(--surface2);border:1px solid var(--line)}
input[type=file]{display:none}.pathbar{display:flex;gap:8px;margin-top:12px}.pathbar input{min-width:0;flex:1;background:var(--surface);border:1px solid var(--line);color:var(--text);padding:11px;border-radius:9px}
.hidden{display:none!important}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:20px 0}.metric,.panel{border:1px solid var(--line);background:linear-gradient(145deg,var(--surface2),var(--surface));border-radius:14px;padding:17px}.metric .n{font-size:27px;font-weight:750}.metric .l{color:var(--muted);font-size:12px}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel h2{font-size:15px;margin:0 0 14px;color:#cfe8ff}.kv{display:grid;grid-template-columns:130px 1fr;gap:8px;border-bottom:1px solid #23314a;padding:8px 0}.kv span:first-child{color:var(--muted)}
.pill{display:inline-block;padding:4px 9px;border-radius:20px;background:#1a2a43;margin:3px;color:#bed4ef}.finding{border-left:3px solid var(--red);padding:9px 12px;background:#21131b;margin:8px 0;border-radius:4px}.finding.low{border-color:#e7c65e}
pre{white-space:pre-wrap;word-break:break-word;color:#b9c8dc;max-height:360px;overflow:auto}.empty{color:var(--muted)}.loader{width:24px;height:24px;border:3px solid #273954;border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite;margin:auto}@keyframes spin{to{transform:rotate(360deg)}}
footer{color:var(--muted);text-align:center;padding:34px}@media(max-width:800px){.hero,.columns{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}.tag{display:none}}
nav.tabs{display:flex;gap:8px;margin:0 0 22px}nav.tabs button{background:var(--surface2);border:1px solid var(--line);color:var(--muted);font-weight:650}
nav.tabs button.active{background:linear-gradient(90deg,#27bfdc,#7866e8);color:#fff}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #23314a;font-size:13px}th{color:var(--muted);font-weight:600}
code{color:#b7f5ff;word-break:break-all}.ok{color:var(--green)}.bad{color:var(--red)}
.mono{font-family:ui-monospace,monospace;font-size:12px;word-break:break-all;overflow-wrap:anywhere;line-height:1.45}
.kv span:last-child{min-width:0;overflow-wrap:anywhere}
</style></head>
<body><header><div class="mark">A</div><div><div class="brand">APEX</div><div class="tag">ANDROID PACKAGE EXAMINER</div></div><div class="spacer"></div><div id="health" class="status">● Engine ready</div></header>
<main>
<nav class="tabs"><button id="tabAnalyze" class="active">Analyze</button><button id="tabDevices">Devices</button><button id="tabCorpus">Corpus</button></nav>
<div id="viewDevices" class="hidden">
<div class="panel"><h2>Connected devices</h2><div style="display:flex;gap:8px;margin-bottom:12px"><button id="devRefresh" class="secondary">Refresh devices</button></div><div id="deviceList"><span class="empty">Loading…</span></div></div>
<div class="panel" style="margin-top:14px"><h2>Device packages</h2><div class="pathbar"><input id="devSerial" placeholder="device serial"><button id="devPackages" class="secondary">List packages</button><button id="devSync">Sync to corpus</button></div><div id="packageList" style="margin-top:12px;max-height:420px;overflow:auto"><span class="empty">Select a device to list installed packages.</span></div></div>
<div class="panel" style="margin-top:14px"><p class="tag">APEX reads packages from a device you have authorized over ADB. Nothing leaves this machine.</p></div>
</div>
<div id="viewCorpus" class="hidden">
<div class="panel"><h2>Local corpus</h2><div class="pathbar"><input id="corpusDb" placeholder="~/.apex/corpus.db"><button id="corpusGo" class="secondary">Load stats</button></div><div id="corpusStats" style="margin-top:14px"><span class="empty">Load the corpus index to see statistics.</span></div></div>
<div class="panel" style="margin-top:14px"><h2>Indexed packages</h2><div id="corpusPackages"><span class="empty">No corpus loaded.</span></div></div>
</div>
<div id="viewAnalyze">
<section class="hero"><div><h1>Understand any APK.<br><span class="gradient">Before it understands you.</span></h1><p class="lead">Inspect manifests, permissions, resources, DEX classes, native libraries, and static security signals from one private local workspace.</p></div>
<div><div id="drop" class="drop"><div><strong>Drop an APK or IPA here</strong><p>Android and iOS · files stay on this machine.</p><label class="button" for="file">Choose file</label><input id="file" type="file" accept=".apk,.zip,.ipa"></div></div><div class="pathbar"><input id="path" placeholder="/path/to/application.apk or .ipa"><button id="pathGo" class="secondary">Open path</button></div></div></section>
<section id="busy" class="panel hidden"><div class="loader"></div><p style="text-align:center;color:var(--muted)">Analyzing package structure and security signals…</p></section>
<section id="results" class="hidden">
<div style="display:flex;align-items:center;gap:12px"><div><h2 id="filename" style="font-size:22px;margin:0"></h2><div id="hash" class="tag"></div></div><span id="platformBadge" class="pill"></span><div class="spacer"></div><button id="sbom" class="secondary">Download SBOM</button><button id="decompile" class="secondary">Decompile Java</button></div>
<div class="grid"><div class="metric"><div id="entries" class="n">0</div><div id="lblEntries" class="l">ARCHIVE ENTRIES</div></div><div class="metric"><div id="dex" class="n">0</div><div id="lblDex" class="l">DEX CLASSES</div></div><div class="metric"><div id="perms" class="n">0</div><div id="lblPerms" class="l">PERMISSIONS</div></div><div class="metric"><div id="trackers" class="n">0</div><div class="l">TRACKERS</div></div><div class="metric"><div id="posture" class="n">—</div><div class="l">PRIVACY GRADE</div></div><div class="metric"><div id="risk" class="n">—</div><div class="l">SECURITY VERDICT</div></div></div>
<div class="columns"><div class="panel"><h2>Application identity</h2><div id="identity"></div></div><div class="panel"><h2 id="componentsTitle">Entry points</h2><div id="components"></div></div><div class="panel"><h2>Trackers &amp; libraries</h2><div id="intel"></div></div><div class="panel"><h2>Privacy posture</h2><div id="posturePanel"></div></div><div class="panel"><h2 id="permsTitle">Permissions</h2><div id="permissions"></div></div><div class="panel"><h2>Security findings</h2><div id="findings"></div></div></div>
<div class="panel" style="margin-top:14px" id="signingCard"><h2>Signing &amp; certificates</h2><div id="signing"></div></div>
<div class="panel" style="margin-top:14px"><h2>Native architectures & resource table</h2><div id="technical"></div></div>
<div class="panel" style="margin-top:14px"><h2>Class & method explorer</h2><div class="pathbar"><input id="classSearch" placeholder="Search classes and methods"><button id="classGo" class="secondary">Search</button></div><div id="classList" style="margin-top:12px;max-height:430px;overflow:auto"></div></div>
</section></div></main><footer>APEX runs locally · Static analysis is not a malware verdict</footer>
<script>
let currentPath="", currentData=null;
const $=id=>document.getElementById(id), esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function busy(v){$("busy").classList.toggle("hidden",!v);if(v)$("results").classList.add("hidden")}
function kv(k,v){return `<div class="kv"><span>${esc(k)}</span><span>${esc(v||"—")}</span></div>`}
function pills(items){return items?.length?items.map(x=>`<span class="pill">${esc(x)}</span>`).join(""):'<span class="empty">None detected</span>'}
function renderClasses(query=""){const d=currentData?.dex||{},q=query.toLowerCase(),methods=d.methods||[],classes=(d.classes||[]).filter(c=>!q||c.name.toLowerCase().includes(q)||methods.some(m=>m.class===c.name&&(m.name+m.descriptor).toLowerCase().includes(q)));$("classList").innerHTML=classes.slice(0,300).map(c=>{const classMatches=!q||c.name.toLowerCase().includes(q),ms=methods.filter(m=>m.class===c.name&&(classMatches||(m.name+m.descriptor).toLowerCase().includes(q)));return `<details><summary><code>${esc(c.name)}</code> <span class="tag">${esc(c.access||"")}</span></summary>${ms.map(m=>`<div class="kv"><span>${esc(m.access)}</span><code>${esc(m.name+m.descriptor)}</code></div>`).join("")||'<div class="empty">No matching methods</div>'}</details>`}).join("")||'<span class="empty">No matching DEX classes.</span>'}
function renderIntel(intel){const t=intel?.trackers||[],l=intel?.libraries||[];if(!t.length&&!l.length){$("intel").innerHTML='<span class="empty">No trackers or known libraries detected.</span>';return}
const row=d=>`<div class="finding ${d.kind==="tracker"?"":"low"}"><strong>${esc(d.name)}</strong> <span class="tag">${esc(d.kind)}</span> ${(d.categories||[]).map(c=>`<span class="pill">${esc(c)}</span>`).join("")}<br><small class="mono">${esc((d.evidence||[]).slice(0,3).join(", "))}</small></div>`;
$("intel").innerHTML=(t.length?`<p class="tag">${t.length} tracker SDK(s)</p>`+t.map(row).join(""):"")+(l.length?`<p class="tag">${l.length} librar${l.length===1?"y":"ies"}</p>`+l.map(row).join(""):"")}
function renderPosture(p){if(!p){$("posturePanel").innerHTML='<span class="empty">No posture data.</span>';return}
const cats=Object.entries(p.signals?.tracker_categories||{}).map(([k,v])=>`<span class="pill">${esc(k)}: ${v}</span>`).join("")||'<span class="empty">none</span>';
const disc=(p.discrepancies||[]).length?p.discrepancies.map(d=>`<div class="finding ${d.severity==="low"?"low":""}"><strong>${esc(d.severity)}</strong> · ${esc(d.message)}</div>`).join(""):'<span class="empty">No declared-vs-actual discrepancies.</span>';
$("posturePanel").innerHTML=kv("Grade",`${esc(p.grade)} (${esc(p.score)}/100)`)+kv("Trackers",p.signals?.tracker_count??0)+`<div class="kv"><span>Categories</span><span>${cats}</span></div>`+kv("High-risk perms",p.signals?.dangerous_permission_count??0)+kv("Cleartext traffic",p.signals?.cleartext_traffic?"permitted":"no")+`<div style="margin-top:10px">${disc}</div><p class="tag">${esc(p.disclaimer||"")}</p>`}
function render(data){currentPath=data.path;currentData=data;$("results").classList.remove("hidden");
$("platformBadge").textContent=(data.platform||"android").toUpperCase();
$("trackers").textContent=(data.intelligence?.tracker_count)??0;$("posture").textContent=data.privacy_posture?.grade||"—";
renderIntel(data.intelligence);renderPosture(data.privacy_posture);
if(data.platform==="ios"){return renderIos(data)}
const i=data.inspect,s=data.security,m=i.manifest||{};
$("signingCard").classList.remove("hidden");$("decompile").classList.remove("hidden");$("permsTitle").textContent="Permissions";$("componentsTitle").textContent="Entry points";
$("lblEntries").textContent="ARCHIVE ENTRIES";$("lblDex").textContent="DEX CLASSES";$("lblPerms").textContent="PERMISSIONS";
$("filename").textContent=i.path.split(/[\\/]/).pop();$("hash").textContent=i.sha256;$("entries").textContent=i.entry_count;$("dex").textContent=(data.dex?.classes||[]).length;$("perms").textContent=(m.permissions||[]).length;$("risk").textContent=s.verdict;
$("identity").innerHTML=kv("Package",m.package)+kv("Version",`${m.version_name||"?"} (${m.version_code||"?"})`)+kv("SDK",`min ${m.min_sdk||"?"} · target ${m.target_sdk||"?"}`)+kv("Main activity",m.main_activity);
$("components").innerHTML=pills([...(m.activities||[]),...(m.services||[]),...(m.receivers||[]),...(m.providers||[])]);
$("permissions").innerHTML=pills(m.permissions||[]);$("findings").innerHTML=s.findings.length?s.findings.map(f=>`<div class="finding ${esc(f.severity)}"><strong>${esc(f.category)}</strong> · ${esc(f.message)}<br><small>${esc(f.evidence||"")} ${f.masvs?`· ${esc(f.masvs)}`:""}</small></div>`).join(""):'<span class="empty">No static security findings.</span>';
$("technical").innerHTML=kv("Format",(i.format||"apk").toUpperCase())+kv("DEX files",(i.dex_files||[]).join(", ")||"none")+kv("Native ABIs",(i.native_abis||[]).join(", ")||"none")+kv("Resource packages",(i.resource_table?.packages||[]).join(", ")||"none")+kv("Locales",(i.resource_table?.locales||[]).join(", ")||"none");renderSigning(data.signing);renderClasses()}
function renderIos(data){const r=data.ios||{},a=r.app||{},b=r.binary||{},s=data.security;
$("signingCard").classList.add("hidden");$("decompile").classList.add("hidden");$("permsTitle").textContent="Embedded frameworks";$("componentsTitle").textContent="Privacy manifest";
$("lblEntries").textContent="FRAMEWORKS";$("lblDex").textContent="LINKED DYLIBS";$("lblPerms").textContent="ARCHITECTURES";
$("filename").textContent=(r.path||"").split(/[\\/]/).pop();$("hash").textContent=r.sha256||"";$("entries").textContent=(r.frameworks||[]).length;$("dex").textContent=(b.dylibs||[]).length;$("perms").textContent=(b.architectures||[]).length;$("risk").textContent=s.verdict;
$("identity").innerHTML=kv("Bundle ID",a.bundle_id)+kv("Name",a.name)+kv("Version",`${a.version||"?"} (${a.build||"?"})`)+kv("Min iOS",a.minimum_os)+kv("Executable",a.executable);
const pm=r.privacy_manifest||{};$("components").innerHTML=pm.present?kv("Tracking",pm.tracking?"declared":"not declared")+kv("Tracking domains",(pm.tracking_domains||[]).join(", ")||"none")+kv("Collected data",(pm.collected_data_types||[]).join(", ")||"none"):'<span class="empty">No PrivacyInfo.xcprivacy present.</span>';
$("permissions").innerHTML=pills(r.frameworks||[]);
$("findings").innerHTML=s.findings.length?s.findings.map(f=>`<div class="finding ${esc(f.severity)}"><strong>${esc(f.category)}</strong> · ${esc(f.message)}<br><small>${esc(f.evidence||"")} ${f.masvs?`· ${esc(f.masvs)}`:""}</small></div>`).join(""):'<span class="empty">No static security findings.</span>';
$("technical").innerHTML=kv("Architectures",(b.architectures||[]).map(x=>x.arch).join(", ")||"none")+kv("PIE / ASLR",b.pie?"yes":"no")+kv("Stack canary",b.has_stack_canary?"yes":"no")+kv("ARC",b.has_arc?"yes":"no")+kv("Encrypted",b.encrypted?"yes (FairPlay)":"no")+kv("Code signature",b.has_code_signature?"present":"absent")+kv("Linked dylibs",(b.dylibs||[]).length);
$("classList").innerHTML=(b.dylibs||[]).map(x=>`<div class="kv"><span></span><code>${esc(x)}</code></div>`).join("")||'<span class="empty">No linked libraries.</span>'}
function renderSigning(sg){if(!sg){$("signing").innerHTML='<span class="empty">No signing data.</span>';return}
const sch=Object.entries(sg.schemes||{}).map(([k,v])=>`<span class="pill">${esc(k)} ${v?'<span class="ok">✓</span>':'<span class="bad">✗</span>'}</span>`).join("");
const cc=sg.cross_check||{};const ccText=cc.status==="match"?'<span class="ok">apksigner agrees</span>':cc.status==="mismatch"?`<span class="bad">apksigner differs: ${esc((cc.differences||[]).join("; "))}</span>`:'<span class="tag">apksigner cross-check not available (native result shown)</span>';
$("signing").innerHTML=kv("Signed",sg.signed?"yes":"no")+kv("Engine",sg.provider)+`<div class="kv"><span>Schemes</span><span>${sch}</span></div>`+kv("Subject",sg.subject)+kv("Issuer",sg.issuer)+`<div class="kv"><span>SHA-256</span><span class="mono">${esc(sg.fingerprint_sha256||"—")}</span></div>`+`<div class="kv"><span>SHA-1</span><span class="mono">${esc(sg.fingerprint_sha1||"—")}</span></div>`+kv("Valid from",sg.not_valid_before)+kv("Valid until",sg.not_valid_after)+kv("Self-signed",sg.self_signed===undefined?"—":(sg.self_signed?"yes":"no"))+kv("Signers",sg.signer_count)+`<div class="kv"><span>Cross-check</span><span>${ccText}</span></div>`+(sg.warnings?.length?`<div class="finding low">${sg.warnings.map(esc).join("<br>")}</div>`:"")+(sg.trust_note?`<p class="tag">${esc(sg.trust_note)}</p>`:"")}
function showTab(name){for(const t of ["Analyze","Devices","Corpus"]){$("view"+t).classList.toggle("hidden",t!==name);$("tab"+t).classList.toggle("active",t===name)}}
$("tabAnalyze").onclick=()=>showTab("Analyze");$("tabDevices").onclick=()=>{showTab("Devices");loadDevices()};$("tabCorpus").onclick=()=>showTab("Corpus");
async function loadDevices(){$("deviceList").innerHTML='<span class="empty">Loading…</span>';try{const r=await fetch("/api/devices");const d=await r.json();const devs=d.devices||[];
$("deviceList").innerHTML=devs.length?`<table><tr><th>Serial</th><th>State</th><th>Model</th><th></th></tr>${devs.map(x=>`<tr><td><code>${esc(x.serial)}</code></td><td>${x.state==="device"?'<span class="ok">ready</span>':`<span class="bad">${esc(x.state)}</span>`}</td><td>${esc(x.model||"—")}</td><td><button class="secondary" onclick="selectDevice('${esc(x.serial)}')">Select</button></td></tr>`).join("")}</table>`:`<span class="empty">No devices detected. Connect a device with USB debugging or wireless debugging authorized.${d.hint?" "+esc(d.hint):""}</span>`}catch(e){$("deviceList").innerHTML=`<span class="empty">${esc(e.message)}</span>`}}
function selectDevice(s){$("devSerial").value=s;listPackages()}
async function listPackages(){const serial=$("devSerial").value.trim();if(!serial)return alert("Enter or select a device serial");$("packageList").innerHTML='<div class="loader"></div>';try{const r=await fetch("/api/devices/"+encodeURIComponent(serial)+"/packages");const d=await r.json();if(!r.ok)throw Error(d.error||"Failed");const ps=d.packages||[];
$("packageList").innerHTML=ps.length?`<table><tr><th>Package</th><th>Type</th><th>Path</th></tr>${ps.map(p=>`<tr><td><code>${esc(p.package)}</code></td><td>${p.system?"system":"user"}</td><td class="mono">${esc(p.apk_path)}</td></tr>`).join("")}</table>`:'<span class="empty">No packages returned.</span>'}catch(e){$("packageList").innerHTML=`<span class="empty">${esc(e.message)}</span>`}}
$("devRefresh").onclick=loadDevices;$("devPackages").onclick=listPackages;
$("devSync").onclick=async()=>{const serial=$("devSerial").value.trim();if(!serial)return alert("Enter or select a device serial");if(!confirm("Sync installed packages from "+serial+" into the local corpus?"))return;$("packageList").innerHTML='<div class="loader"></div>';try{const r=await fetch("/api/devices/"+encodeURIComponent(serial)+"/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const d=await r.json();if(!r.ok)throw Error(d.error||"Sync failed");$("packageList").innerHTML=`<p class="ok">Sync complete: ${d.changed} analyzed, ${d.skipped} unchanged.</p>`}catch(e){$("packageList").innerHTML=`<span class="empty">${esc(e.message)}</span>`}};
async function loadCorpus(){const db=$("corpusDb").value.trim();const q=db?"?db="+encodeURIComponent(db):"";try{const r=await fetch("/api/corpus/stats"+q);const d=await r.json();if(!r.ok)throw Error(d.error||"Failed");
$("corpusStats").innerHTML=`<div class="grid"><div class="metric"><div class="n">${d.package_count??0}</div><div class="l">PACKAGES</div></div><div class="metric"><div class="n">${d.snapshot_count??0}</div><div class="l">SNAPSHOTS</div></div><div class="metric"><div class="n">${d.artifact_count??0}</div><div class="l">ARTIFACTS</div></div><div class="metric"><div class="n">${esc(d.serial||"all")}</div><div class="l">SCOPE</div></div></div>`;
const pr=await fetch("/api/corpus/packages"+q);const pd=await pr.json();const rows=pd.packages||[];
$("corpusPackages").innerHTML=rows.length?`<table><tr><th>Package</th><th>Version</th><th>Report</th></tr>${rows.map(p=>`<tr><td><code>${esc(p.package_name)}</code></td><td>${esc(p.version_name||"")} (${esc(p.version_code??"")})</td><td class="mono">${esc(p.report_path||"—")}</td></tr>`).join("")}</table>`:'<span class="empty">No packages indexed yet. Run a device sync.</span>'}catch(e){$("corpusStats").innerHTML=`<span class="empty">${esc(e.message)}</span>`}}
$("corpusGo").onclick=loadCorpus;
async function pathAnalyze(path){busy(true);try{const r=await fetch("/api/open",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path})});const d=await r.json();if(!r.ok)throw Error(d.error||"Analysis failed");render(d)}catch(e){alert(e.message)}finally{busy(false)}}
async function upload(file){if(!file)return;busy(true);try{const r=await fetch("/api/upload?name="+encodeURIComponent(file.name),{method:"POST",body:file});const d=await r.json();if(!r.ok)throw Error(d.error||"Upload failed");render(d)}catch(e){alert(e.message)}finally{busy(false)}}
$("file").onchange=e=>upload(e.target.files[0]);$("pathGo").onclick=()=>pathAnalyze($("path").value);
$("classGo").onclick=()=>renderClasses($("classSearch").value);$("classSearch").oninput=e=>renderClasses(e.target.value);
const drop=$("drop");["dragenter","dragover"].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.add("drag")}));["dragleave","drop"].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.remove("drag")}));drop.addEventListener("drop",e=>upload(e.dataTransfer.files[0]));
$("decompile").onclick=async()=>{if(!currentPath)return;const r=await fetch("/api/decompile",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:currentPath})});const d=await r.json();alert(r.ok?`Decompiled ${d.class_count} classes to ${d.output}`:d.error)};
$("sbom").onclick=async()=>{if(!currentPath)return;const r=await fetch("/api/sbom",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:currentPath})});const d=await r.json();if(!r.ok)return alert(d.error||"SBOM failed");const blob=new Blob([JSON.stringify(d,null,2)],{type:"application/json"});const u=URL.createObjectURL(blob);const a=document.createElement("a");a.href=u;a.download="apex-sbom.cdx.json";a.click();URL.revokeObjectURL(u)};
fetch("/api/health").then(r=>r.json()).then(d=>$("health").textContent=d.ready?"● Engine ready":"● Setup required").catch(()=>$("health").textContent="● Engine unavailable");
</script></body></html>"""


class ApexWebHandler(BaseHTTPRequestHandler):
    server_version = f"APEX/{__version__}"

    def _json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, maximum: int = 512 * 1024 * 1024) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length > maximum:
            raise ApexError(f"request is larger than the {maximum // (1024 * 1024)} MiB limit")
        return self.rfile.read(length)

    def _payload(self) -> dict:
        try:
            return json.loads(self._body().decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApexError("request body must be JSON") from exc

    def _analyze_path(self, path: Path) -> dict:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise ApexError(f"application not found: {resolved}")
        if resolved.suffix.lower() == ".ipa":
            return self._analyze_ios(resolved)
        dex = {"classes": [], "methods": [], "edges": [], "errors": []}
        with zipfile.ZipFile(resolved) as archive:
            for name in sorted(
                item
                for item in archive.namelist()
                if re.fullmatch(r"(?:.*/)?classes\d*\.dex", item)
            ):
                try:
                    metadata = dex_metadata(archive.read(name), name)
                    for key in ("classes", "methods", "edges"):
                        dex[key].extend(metadata[key])
                except Exception as exc:
                    dex["errors"].append({"dex": name, "error": str(exc)})
        native = analyze_signatures(resolved)
        native["cross_check"] = cross_check_with_apksigner(resolved, native)
        info = inspect_apk(resolved)
        manifest = info.get("manifest", {})
        detections = detect_android(
            [cls.get("name", "") for cls in dex["classes"] if cls.get("name")]
        )
        posture = assess_posture(
            platform="android",
            permissions=manifest.get("permissions", []),
            detections=detections,
            cleartext=bool(manifest.get("uses_cleartext_traffic")),
        )
        return {
            "platform": "android",
            "path": str(resolved),
            "inspect": info,
            "security": security_scan(resolved),
            "signing": format_signing_panel(native),
            "dex": dex,
            "intelligence": summarize_detections(detections),
            "privacy_posture": posture,
        }

    def _analyze_ios(self, resolved: Path) -> dict:
        from apex.ios.ipa import inspect_ipa

        report = inspect_ipa(resolved)
        detections = list(report.get("trackers", [])) + list(report.get("libraries", []))
        ats_insecure = any(
            f.get("category") == "ios-transport-security" for f in report.get("findings", [])
        )
        posture = assess_posture(
            platform="ios",
            permissions=[],
            detections=detections,
            cleartext=ats_insecure,
            privacy_manifest=report.get("privacy_manifest"),
        )
        findings = report.get("findings", [])
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        highest = max((order.get(str(f.get("severity")), 1) for f in findings), default=0)
        verdict = "HIGH_RISK" if highest >= 3 else ("REVIEW" if findings else "CLEAN")
        return {
            "platform": "ios",
            "path": str(resolved),
            "ios": report,
            "security": {
                "verdict": verdict,
                "findings": findings,
                "finding_count": len(findings),
            },
            "intelligence": summarize_detections(detections),
            "privacy_posture": posture,
        }

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            body = WEB_APP.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/health":
            self._json(doctor())
        elif path == "/api/devices":
            self._json(
                {
                    "devices": list_connected(),
                    "hint": None
                    if get_adb_command()
                    else "adb was not found. Run: apex doctor",
                }
            )
        elif re.fullmatch(r"/api/devices/[^/]+/packages", path):
            serial = unquote(path.split("/")[3])
            packages = list_packages(serial)
            self._json(
                {
                    "serial": serial,
                    "packages": [
                        {
                            "package": item.package,
                            "apk_path": item.apk_path,
                            "system": item.system,
                        }
                        for item in packages
                    ],
                }
            )
        elif path == "/api/corpus/stats":
            query = parse_qs(urlparse(self.path).query)
            db = query.get("db", [""])[0] or str(Path.home() / ".apex" / "corpus.db")
            serial = query.get("serial", [None])[0]
            self._json(corpus_stats(Path(db), serial=serial))
        elif path == "/api/corpus/packages":
            query = parse_qs(urlparse(self.path).query)
            db = query.get("db", [""])[0] or str(Path.home() / ".apex" / "corpus.db")
            self._json({"packages": corpus_packages(Path(db))})
        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path)
        try:
            if route.path == "/api/open":
                payload = self._payload()
                self._json(self._analyze_path(Path(str(payload.get("path", "")))))
                return
            if route.path == "/api/upload":
                filename = parse_qs(route.query).get("name", ["application.apk"])[0]
                safe_name = sanitized_zip_name(Path(filename).name)
                if not safe_name:
                    raise ApexError("invalid upload filename")
                upload_root = Path(getattr(self.server, "workspace"))
                upload_root.mkdir(parents=True, exist_ok=True)
                destination = upload_root / safe_name
                destination.write_bytes(self._body())
                self._json(self._analyze_path(destination))
                return
            sync_match = re.fullmatch(r"/api/devices/([^/]+)/sync", route.path)
            if sync_match:
                serial = unquote(sync_match.group(1))
                payload = self._payload() if int(self.headers.get("Content-Length", "0")) else {}
                db = Path(str(payload.get("db") or Path.home() / ".apex" / "corpus.db"))
                self._json(sync_device(serial, db, user_id=int(payload.get("user", 0))))
                return
            if route.path == "/api/sbom":
                payload = self._payload()
                app = Path(str(payload.get("path", ""))).expanduser().resolve()
                if not app.is_file():
                    raise ApexError(f"application not found: {app}")
                self._json(generate_sbom(app))
                return
            if route.path == "/api/decompile":
                payload = self._payload()
                apk = Path(str(payload.get("path", ""))).resolve()
                if not apk.is_file():
                    raise ApexError(f"APK not found: {apk}")
                output = Path(getattr(self.server, "workspace")) / f"{apk.stem}-decompiled"
                result = decompile_apk(apk, output)
                self._json(
                    {
                        "output": str(output),
                        "class_count": len(result["classes"]),
                        "errors": result["errors"],
                    }
                )
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ApexError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # avoid leaking a stack trace to the browser
            self._json({"error": f"operation failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        # Keep CLI output useful; health polling should not flood it.
        if self.path != "/api/health":
            super().log_message(format, *args)


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    workspace: Path | None = None,
    open_browser: bool = True,
) -> None:
    workspace = workspace or Path(tempfile.gettempdir()) / "apex-web"
    server = ThreadingHTTPServer((host, port), ApexWebHandler)
    server.workspace = str(workspace)  # type: ignore[attr-defined]
    url = f"http://{host}:{port}"
    print(f"APEX web UI: {url}")
    print(f"Workspace: {workspace}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
