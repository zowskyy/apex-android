// server/inference.js - Lightweight HTTP server for GGUF models
// Communicates with llama.cpp via child process. No native deps.

const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const IM_END = '<|' + 'im_end' + '|>';

class InferenceServer {
  constructor(config = {}) {
    this.config = {
      port: config.port || 8899,
      modelPath: config.modelPath || path.join(__dirname, '..', 'models', 'codeqwen-7b-q4.gguf'),
      threads: config.threads || Math.max(1, require('os').cpus().length - 1),
      contextSize: config.contextSize || 4096,
      llamaBin: config.llamaBin || 'llama-cli',
      ...config
    };

    this.process = null;
    this.app = express();
    this.app.use(express.json({ limit: '10mb' }));
    this.setupRoutes();
  }

  setupRoutes() {
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'ok',
        model: path.basename(this.config.modelPath),
        uptime: process.uptime()
      });
    });

    this.app.post('/v1/chat/completions', async (req, res) => {
      try {
        const { messages, temperature = 0.1, max_tokens = 2048 } = req.body;

        let prompt = '';
        for (const msg of messages) {
          if (msg.role === 'system') {
            prompt += `<|im_start|>system\n${msg.content}${IM_END}\n`;
          } else if (msg.role === 'user') {
            prompt += `<|im_start|>user\n${msg.content}${IM_END}\n`;
          }
        }
        prompt += '<|im_start|>assistant\n';

        const response = await this.runInference(prompt, { temperature, max_tokens });

        res.json({
          choices: [{
            message: { role: 'assistant', content: response },
            finish_reason: 'stop'
          }]
        });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    this.app.get('/v1/models', (req, res) => {
      res.json({
        models: [{
          id: path.basename(this.config.modelPath),
          object: 'model'
        }]
      });
    });

    this.app.post('/generate', async (req, res) => {
      try {
        const { prompt, temperature, max_tokens } = req.body;
        const response = await this.runInference(prompt, { temperature, max_tokens });
        res.json({ response });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // Serve web UI
    this.app.use(express.static(path.join(__dirname, '..', 'ui')));
  }

  findLlamaBinary() {
    const candidates = [
      this.config.llamaBin,
      'llama-cli',
      'llama.cpp',
      'main',
      path.join(__dirname, '..', 'llama.cpp', 'build', 'bin', 'llama-cli')
    ];

    for (const bin of candidates) {
      try {
        require('child_process').execSync(`command -v ${bin}`, { stdio: 'ignore' });
        return bin;
      } catch {
        if (fs.existsSync(bin)) return bin;
      }
    }
    return this.config.llamaBin;
  }

  async runInference(prompt, options = {}) {
    return new Promise((resolve, reject) => {
      if (!fs.existsSync(this.config.modelPath)) {
        reject(new Error(`Model not found: ${this.config.modelPath}. Run: bash installer.sh`));
        return;
      }

      const llamaBin = this.findLlamaBinary();
      const llamaProcess = spawn(llamaBin, [
        '-m', this.config.modelPath,
        '-p', prompt,
        '-n', String(options.max_tokens || 2048),
        '--temp', String(options.temperature || 0.1),
        '-t', String(this.config.threads),
        '-c', String(this.config.contextSize),
        '--no-display-prompt'
      ], {
        timeout: 60000
      });

      let output = '';
      let error = '';

      llamaProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      llamaProcess.stderr.on('data', (data) => {
        error += data.toString();
      });

      llamaProcess.on('close', (code) => {
        if (code !== 0 && !output) {
          reject(new Error(error || `llama.cpp exited with code ${code}`));
        } else {
          resolve(output.trim());
        }
      });

      llamaProcess.on('error', (err) => {
        reject(new Error(
          `Failed to start llama.cpp. Install from: https://github.com/ggerganov/llama.cpp\n${err.message}`
        ));
      });
    });
  }

  async start() {
    return new Promise((resolve) => {
      this.server = this.app.listen(this.config.port, () => {
        console.log(`🧠 Inference server: http://localhost:${this.config.port}`);
        console.log(`📦 Model: ${path.basename(this.config.modelPath)}`);
        console.log(`🌐 Web UI: http://localhost:${this.config.port}/index.html`);
        resolve();
      });
    });
  }

  async stop() {
    if (this.process) {
      this.process.kill();
    }
    if (this.server) {
      this.server.close();
    }
    console.log('🛑 Server stopped');
  }
}

if (require.main === module) {
  const server = new InferenceServer();
  server.start();

  process.on('SIGINT', async () => {
    await server.stop();
    process.exit(0);
  });
}

module.exports = { InferenceServer };
