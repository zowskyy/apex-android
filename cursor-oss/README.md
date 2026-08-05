# Cursor OSS — Free Offline Coding Agent

Zero subscription. Fully offline. Built for every community.

Cursor OSS runs a 4-stage **ARC cycle** (Analysis → Plan → Code → Review) with self-refinement, using local GGUF models via `llama.cpp`. No cloud APIs, no accounts, no telemetry.

## Quick Start

```bash
cd cursor-oss
bash installer.sh          # install deps + download model (~4GB)
node server/inference.js   # start inference server + web UI
```

Open **http://localhost:8899/index.html** in any browser (phone, tablet, or desktop).

## Interfaces

| Interface | Command | Use case |
|-----------|---------|----------|
| **Web UI** | `node server/inference.js` → open `/index.html` | Phone, tablet, visual workflow |
| **CLI** | `node ui/cli.js "build a todo app"` | Headless (RPi, Termux, SSH) |
| **VS Code** | Install via `.vscode/package.json` manifest | IDE integration (optional) |

### CLI Examples

```bash
node ui/cli.js "Fix the off-by-one error in my loop"
node ui/cli.js idea "A water pump maintenance tracker for my village"
```

## Architecture

```
cursor-oss/
├── core/
│   ├── agent.js       # ARC cycle engine (pure JS)
│   ├── prompts.js     # Stage templates + language support
│   ├── context.js     # Lightweight codebase scanner
│   └── project.js     # Save/load projects
├── server/
│   └── inference.js   # HTTP server → llama.cpp
├── ui/
│   ├── index.html     # Single-file web app
│   ├── cli.js         # Terminal interface
│   └── vscode-bridge.js
├── models/            # GGUF model storage
└── projects/          # Saved project data
```

## Dependencies

Only 3 runtime dependencies: `express`, `minisearch`, `marked`. No native Node compilation required.

## Requirements

- **Node.js** 16+
- **llama.cpp** (`llama-cli` binary) — [install guide](https://github.com/ggerganov/llama.cpp)
- **~4GB disk** for quantized model
- **2GB+ RAM** recommended

## Testing (no model required)

```bash
npm test
```

Validates prompt templates, context scanner, project save/load, and JSON parsing — without downloading or loading a model.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Inference port | `8899` | HTTP server port |
| Model path | `models/codeqwen-7b-q4.gguf` | GGUF model file |
| Review loops | `2` | Max refinement iterations |
| Quality threshold | `0.80` | Minimum review score |

## License

MIT — free for all communities.
