"""Dependency-free local web interface for APEX."""

from __future__ import annotations

import json
import re
import socket
import tempfile
import threading
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .analysis import ApexError, dex_metadata, inspect_apk, sanitized_zip_name
from .workflows import decompile_apk, doctor, security_scan

WEB_APP = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="APEX">
<meta name="theme-color" content="#070b13">
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
button,.button{border:0;border-radius:9px;padding:12px 16px;background:linear-gradient(90deg,#27bfdc,#7866e8);color:white;font-weight:700;cursor:pointer;font-size:15px}.secondary{background:var(--surface2);border:1px solid var(--line)}
input[type=file]{display:none}.pathbar{display:flex;gap:8px;margin-top:12px}.pathbar input{min-width:0;flex:1;background:var(--surface);border:1px solid var(--line);color:var(--text);padding:11px;border-radius:9px}
.mobile-only{display:none}.desktop-only{display:block}
.hidden{display:none!important}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:20px 0}.metric,.panel{border:1px solid var(--line);background:linear-gradient(145deg,var(--surface2),var(--surface));border-radius:14px;padding:17px}.metric .n{font-size:27px;font-weight:750}.metric .l{color:var(--muted);font-size:12px}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel h2{font-size:15px;margin:0 0 14px;color:#cfe8ff}.kv{display:grid;grid-template-columns:130px 1fr;gap:8px;border-bottom:1px solid #23314a;padding:8px 0}.kv span:first-child{color:var(--muted)}
.pill{display:inline-block;padding:4px 9px;border-radius:20px;background:#1a2a43;margin:3px;color:#bed4ef}.finding{border-left:3px solid var(--red);padding:9px 12px;background:#21131b;margin:8px 0;border-radius:4px}.finding.low{border-color:#e7c65e}
pre{white-space:pre-wrap;word-break:break-word;color:#b9c8dc;max-height:360px;overflow:auto}.empty{color:var(--muted)}.loader{width:24px;height:24px;border:3px solid #273954;border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite;margin:auto}@keyframes spin{to{transform:rotate(360deg)}}
footer{color:var(--muted);text-align:center;padding:34px}@media(max-width:800px){header{padding:0 16px;height:60px}.main-pad{padding:24px 16px}.hero,.columns{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}.tag{display:none}.pathbar.desktop-only{display:none}.mobile-only{display:block}.drop{min-height:180px;padding:20px}.lead{font-size:15px}.kv{grid-template-columns:1fr;gap:2px}}
</style></head>
<body><header><div class="mark">A</div><div><div class="brand">APEX</div><div class="tag">ANDROID PACKAGE EXAMINER</div></div><div class="spacer"></div><div id="health" class="status">● Engine ready</div></header>
<main class="main-pad">
<section class="hero"><div><h1>Understand any APK.<br><span class="gradient">Before it understands you.</span></h1><p class="lead">Inspect manifests, permissions, resources, DEX classes, native libraries, and static security signals from one private local workspace.</p></div>
<div><div id="drop" class="drop"><div><strong>Drop an APK here</strong><p class="mobile-only">Tap to pick an APK from your phone.</p><p class="desktop-only">Files stay on this machine.</p><label class="button" for="file">Choose APK</label><input id="file" type="file" accept=".apk,.zip,application/vnd.android.package-archive"></div></div><div class="pathbar desktop-only"><input id="path" placeholder="/path/to/application.apk"><button id="pathGo" class="secondary">Open path</button></div></div></section>
<section id="busy" class="panel hidden"><div class="loader"></div><p style="text-align:center;color:var(--muted)">Analyzing package structure and security signals…</p></section>
<section id="results" class="hidden">
<div style="display:flex;align-items:center;gap:12px"><div><h2 id="filename" style="font-size:22px;margin:0"></h2><div id="hash" class="tag"></div></div><div class="spacer"></div><button id="decompile" class="secondary">Decompile Java</button></div>
<div class="grid"><div class="metric"><div id="entries" class="n">0</div><div class="l">ARCHIVE ENTRIES</div></div><div class="metric"><div id="dex" class="n">0</div><div class="l">DEX CLASSES</div></div><div class="metric"><div id="perms" class="n">0</div><div class="l">PERMISSIONS</div></div><div class="metric"><div id="risk" class="n">—</div><div class="l">SECURITY VERDICT</div></div></div>
<div class="columns"><div class="panel"><h2>Application identity</h2><div id="identity"></div></div><div class="panel"><h2>Entry points</h2><div id="components"></div></div><div class="panel"><h2>Permissions</h2><div id="permissions"></div></div><div class="panel"><h2>Security findings</h2><div id="findings"></div></div></div>
<div class="panel" style="margin-top:14px"><h2>Native architectures & resource table</h2><div id="technical"></div></div>
<div class="panel" style="margin-top:14px"><h2>Class & method explorer</h2><div class="pathbar"><input id="classSearch" placeholder="Search classes and methods"><button id="classGo" class="secondary">Search</button></div><div id="classList" style="margin-top:12px;max-height:430px;overflow:auto"></div></div>
<div class="panel" style="margin-top:14px"><h2>Code Pilot</h2><p class="tag" style="margin:0 0 10px">Describe what you want — Code Pilot runs APEX tools for you (Pro).</p><div id="pilotLog" style="max-height:220px;overflow:auto;margin-bottom:10px;color:#b9c8dc"></div><div class="pathbar"><input id="pilotPrompt" placeholder="e.g. security-scan this APK and summarize risks"><button id="pilotGo">Ask</button></div></div>
</section></main><footer>APEX runs locally · Static analysis is not a malware verdict</footer>
<script>
let currentPath="", currentData=null;
const $=id=>document.getElementById(id), esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function busy(v){$("busy").classList.toggle("hidden",!v);if(v)$("results").classList.add("hidden")}
function kv(k,v){return `<div class="kv"><span>${esc(k)}</span><span>${esc(v||"—")}</span></div>`}
function pills(items){return items?.length?items.map(x=>`<span class="pill">${esc(x)}</span>`).join(""):'<span class="empty">None detected</span>'}
function renderClasses(query=""){const d=currentData?.dex||{},q=query.toLowerCase(),methods=d.methods||[],classes=(d.classes||[]).filter(c=>!q||c.name.toLowerCase().includes(q)||methods.some(m=>m.class===c.name&&(m.name+m.descriptor).toLowerCase().includes(q)));$("classList").innerHTML=classes.slice(0,300).map(c=>{const classMatches=!q||c.name.toLowerCase().includes(q),ms=methods.filter(m=>m.class===c.name&&(classMatches||(m.name+m.descriptor).toLowerCase().includes(q)));return `<details><summary><code>${esc(c.name)}</code> <span class="tag">${esc(c.access||"")}</span></summary>${ms.map(m=>`<div class="kv"><span>${esc(m.access)}</span><code>${esc(m.name+m.descriptor)}</code></div>`).join("")||'<div class="empty">No matching methods</div>'}</details>`}).join("")||'<span class="empty">No matching DEX classes.</span>'}
function render(data){const i=data.inspect,s=data.security,m=i.manifest||{};currentPath=data.path;currentData=data;$("results").classList.remove("hidden");
$("filename").textContent=i.path.split(/[\\/]/).pop();$("hash").textContent=i.sha256;$("entries").textContent=i.entry_count;$("dex").textContent=(data.dex?.classes||[]).length;$("perms").textContent=(m.permissions||[]).length;$("risk").textContent=s.verdict;
$("identity").innerHTML=kv("Package",m.package)+kv("Version",`${m.version_name||"?"} (${m.version_code||"?"})`)+kv("SDK",`min ${m.min_sdk||"?"} · target ${m.target_sdk||"?"}`)+kv("Main activity",m.main_activity);
$("components").innerHTML=pills([...(m.activities||[]),...(m.services||[]),...(m.receivers||[]),...(m.providers||[])]);
$("permissions").innerHTML=pills(m.permissions||[]);$("findings").innerHTML=s.findings.length?s.findings.map(f=>`<div class="finding ${esc(f.severity)}"><strong>${esc(f.category)}</strong> · ${esc(f.message)}<br><small>${esc(f.evidence||"")}</small></div>`).join(""):'<span class="empty">No static security findings.</span>';
$("technical").innerHTML=kv("Format",(i.format||"apk").toUpperCase())+kv("DEX files",(i.dex_files||[]).join(", ")||"none")+kv("Native ABIs",(i.native_abis||[]).join(", ")||"none")+kv("Resource packages",(i.resource_table?.packages||[]).join(", ")||"none")+kv("Locales",(i.resource_table?.locales||[]).join(", ")||"none");renderClasses()}
async function pathAnalyze(path){busy(true);try{const r=await fetch("/api/open",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path})});const d=await r.json();if(!r.ok)throw Error(d.error||"Analysis failed");render(d)}catch(e){alert(e.message)}finally{busy(false)}}
async function upload(file){if(!file)return;busy(true);try{const r=await fetch("/api/upload?name="+encodeURIComponent(file.name),{method:"POST",body:file});const d=await r.json();if(!r.ok)throw Error(d.error||"Upload failed");render(d)}catch(e){alert(e.message)}finally{busy(false)}}
$("file").onchange=e=>upload(e.target.files[0]);$("pathGo").onclick=()=>pathAnalyze($("path").value);
$("classGo").onclick=()=>renderClasses($("classSearch").value);$("classSearch").oninput=e=>renderClasses(e.target.value);
const drop=$("drop");["dragenter","dragover"].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.add("drag")}));["dragleave","drop"].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.remove("drag")}));drop.addEventListener("drop",e=>upload(e.dataTransfer.files[0]));
$("decompile").onclick=async()=>{if(!currentPath)return;const r=await fetch("/api/decompile",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:currentPath})});const d=await r.json();alert(r.ok?`Decompiled ${d.class_count} classes to ${d.output}`:d.error)};
$("pilotGo").onclick=async()=>{const prompt=$("pilotPrompt").value.trim();if(!prompt)return;const log=$("pilotLog");log.innerHTML+=`<div class="kv"><span>You</span><span>${esc(prompt)}</span></div>`;$("pilotPrompt").value="";try{const r=await fetch("/api/agent",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt,path:currentPath||null,provider:"heuristic"})});const d=await r.json();if(!r.ok)throw Error(d.error||"Code Pilot failed");log.innerHTML+=`<div class="kv"><span>Pilot</span><span>${esc(d.answer)}</span></div>`;log.scrollTop=log.scrollHeight}catch(e){log.innerHTML+=`<div class="finding">${esc(e.message)}</div>`}};
fetch("/api/health").then(r=>r.json()).then(d=>$("health").textContent=d.ready?"● Engine ready":"● Setup required").catch(()=>$("health").textContent="● Engine unavailable");
</script></body></html>"""


class ApexWebHandler(BaseHTTPRequestHandler):
    server_version = "APEX/0.2"

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
            raise ApexError(f"APK not found: {resolved}")
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
        return {
            "path": str(resolved),
            "inspect": inspect_apk(resolved),
            "security": security_scan(resolved),
            "dex": dex,
        }

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            body = WEB_APP.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/health":
            self._json(doctor())
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
            if route.path == "/api/agent":
                from .agent import run_code_pilot
                from .agent.providers import AgentError
                from .edition import EditionError

                payload = self._payload()
                prompt = str(payload.get("prompt", "")).strip()
                if not prompt:
                    raise ApexError("prompt is required")
                path = payload.get("path") or None
                provider = str(payload.get("provider") or "heuristic")
                try:
                    result = run_code_pilot(
                        prompt,
                        apk_path=str(path) if path else None,
                        provider=provider,
                    )
                except (AgentError, EditionError) as exc:
                    raise ApexError(str(exc)) from exc
                self._json(result)
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


def lan_ip() -> str:
    """Best-effort LAN address for phone access instructions."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    workspace: Path | None = None,
    open_browser: bool = True,
    mobile: bool = False,
) -> None:
    if mobile:
        host = "0.0.0.0"
        open_browser = False

    workspace = workspace or Path(tempfile.gettempdir()) / "apex-web"
    server = ThreadingHTTPServer((host, port), ApexWebHandler)
    server.workspace = str(workspace)  # type: ignore[attr-defined]

    if host == "0.0.0.0":
        phone_url = f"http://{lan_ip()}:{port}"
        print("APEX mobile mode — open this URL on your phone (same Wi-Fi):")
        print(f"  {phone_url}")
        print("Only use on a trusted network. Analysis runs on this computer.")
    else:
        print(f"APEX web UI: http://{host}:{port}")

    print(f"Workspace: {workspace}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
