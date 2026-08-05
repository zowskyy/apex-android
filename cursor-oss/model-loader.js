// model-loader.js - Offline model loading with fallbacks
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');
const os = require('os');

class ModelLoader {
  static async load(modelPath, options = {}) {
    // Check if model exists
    if (!fs.existsSync(modelPath)) {
      console.log('📥 Model not found. Checking for available models...');
      return await ModelLoader.downloadModel(modelPath, options);
    }

    console.log(`📦 Loading model: ${path.basename(modelPath)}`);
    
    try {
      const { LlamaModel, LlamaContext, LlamaChatSession } = require('node-llama-cpp');
      
      const model = new LlamaModel({
        modelPath,
        ...options
      });

      const context = new LlamaContext({ model });
      const session = new LlamaChatSession({ context });

      return {
        generate: async (prompt, genOptions = {}) => {
          const response = await session.prompt(prompt, genOptions);
          return response;
        },
        getContext: () => context,
        dispose: () => {
          session.dispose();
          context.dispose();
          model.dispose();
        }
      };
    } catch (err) {
      console.error('Failed to load model:', err);
      throw new Error(`Model load failed: ${err.message}`);
    }
  }

  static async downloadModel(modelPath, options) {
    const models = {
      'codeqwen-7b-q4.gguf': {
        url: 'https://huggingface.co/TheBloke/CodeQwen1.5-7B-Chat-GGUF/resolve/main/codeqwen-1_5-7b-chat-q4_k_m.gguf',
        size: '4.2GB',
        description: 'CodeQwen 7B - Best balance of quality and speed'
      },
      'deepseek-coder-6.7b-q4.gguf': {
        url: 'https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf',
        size: '3.8GB',
        description: 'DeepSeek Coder 6.7B - Strong completion quality'
      },
      'starcoder2-7b-q4.gguf': {
        url: 'https://huggingface.co/TheBloke/StarCoder2-7B-GGUF/resolve/main/starcoder2-7b.Q4_K_M.gguf',
        size: '3.9GB',
        description: 'StarCoder2 7B - Good for fill-in-the-middle'
      }
    };

    console.log('\n📋 Available free models (no subscription required):');
    console.log('─'.repeat(60));
    
    let index = 1;
    for (const [name, info] of Object.entries(models)) {
      console.log(`${index}. ${name}`);
      console.log(`   Size: ${info.size} | ${info.description}\n`);
      index++;
    }

    // Auto-select smallest model for constrained environments
    const totalRAM = os.totalmem() / (1024 * 1024 * 1024); // GB
    let selectedModel = 'codeqwen-7b-q4.gguf';
    
    if (totalRAM <= 8) {
      selectedModel = 'deepseek-coder-6.7b-q4.gguf';
      console.log(`⚠️  Low RAM detected (${totalRAM.toFixed(1)}GB). Selecting smaller model.`);
    }

    const modelInfo = models[selectedModel];
    console.log(`\n📥 Downloading ${selectedModel} (${modelInfo.size})...`);
    console.log('This is a one-time download. The model will work fully offline after this.\n');

    // Download using curl (available on most systems)
    try {
      const modelDir = path.dirname(modelPath);
      if (!fs.existsSync(modelDir)) {
        fs.mkdirSync(modelDir, { recursive: true });
      }

      const targetPath = path.join(modelDir, selectedModel);
      execSync(`curl -L "${modelInfo.url}" -o "${targetPath}" --progress-bar`, {
        stdio: 'inherit',
        timeout: 3600000 // 1 hour timeout for slow connections
      });

      console.log('✅ Model downloaded successfully!');
      return await ModelLoader.load(targetPath, options);
    } catch (err) {
      console.error('❌ Download failed. You can manually download from:');
      console.log(`   ${modelInfo.url}`);
      console.log(`   And place it at: ${modelPath}`);
      throw err;
    }
  }
}

module.exports = { ModelLoader };
