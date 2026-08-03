# APEX on iPhone / iPad

APEX does not ship a native iOS app (App Store policy + Python runtime). Use one of
these wrappers:

## Option A — Phone browser (recommended)

1. On your Mac/PC/Linux box: `apex mobile`
2. On iPhone (same Wi-Fi): open the printed URL in Safari
3. Tap **Share → Add to Home Screen** for a full-screen icon

The web UI already includes `apple-mobile-web-app-*` meta tags.

## Option B — Docker host + phone

```bash
cd wrappers/docker && ./run.sh
```

Open `http://<docker-host-ip>:8765` from Safari on your phone.

## Option C — Tailscale / VPN

If your phone is not on the same LAN, expose APEX only over a private VPN and
open the VPN IP in Safari. Do not expose port 8765 on the public internet.
