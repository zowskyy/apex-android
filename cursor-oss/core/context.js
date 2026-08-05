// core/context.js - Simple file scanner. No native deps.
const fs = require('fs');
const path = require('path');
const MiniSearch = require('minisearch');

class ContextScanner {
  constructor(config = {}) {
    this.config = {
      maxFiles: config.maxFiles || 30,
      maxSnippetSize: config.maxSnippetSize || 1500,
      excludePatterns: config.excludePatterns || [
        'node_modules', '.git', 'dist', 'build',
        '.next', '.cache', '__pycache__',
        '*.min.js', '*.bundle.js', '*.map'
      ],
      ...config
    };

    this.index = new MiniSearch({
      fields: ['path', 'content'],
      storeFields: ['path', 'content'],
      searchOptions: { fuzzy: 0.2, prefix: true }
    });

    this.fileCache = new Map();
    this.initialized = false;
  }

  isCodeFile(filename) {
    const codeExts = ['.js', '.ts', '.jsx', '.tsx', '.py', '.html', '.css',
      '.json', '.md', '.rs', '.go', '.java', '.cpp', '.c',
      '.rb', '.php', '.swift', '.kt', '.dart'];
    return codeExts.some(ext => filename.endsWith(ext));
  }

  shouldExclude(filePath) {
    return this.config.excludePatterns.some(pattern => {
      if (pattern.startsWith('*.')) {
        return filePath.endsWith(pattern.slice(1));
      }
      return filePath.includes(pattern);
    });
  }

  async init(rootDir = '.') {
    if (this.initialized) return;

    const scanDir = async (dir) => {
      try {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (this.shouldExclude(fullPath)) continue;

          if (entry.isDirectory()) {
            await scanDir(fullPath);
          } else if (this.isCodeFile(entry.name)) {
            try {
              const content = fs.readFileSync(fullPath, 'utf-8');
              const snippet = content.substring(0, this.config.maxSnippetSize);
              this.index.add({ id: fullPath, path: fullPath, content: snippet });
              this.fileCache.set(fullPath, content);
            } catch {
              // skip unreadable files
            }
          }
        }
      } catch {
        // skip unreadable directories
      }
    };

    await scanDir(rootDir);
    this.initialized = true;
  }

  async scan(query, context = {}) {
    await this.init(context.rootDir || '.');

    const results = this.index.search(query, { max: 5 });

    const snippets = results.map(r => {
      const content = this.fileCache.get(r.path) || '';
      return `// ${r.path}\n${content.substring(0, this.config.maxSnippetSize)}`;
    });

    let existingCode = '';
    if (context.currentFile) {
      try {
        existingCode = fs.readFileSync(context.currentFile, 'utf-8');
      } catch {
        // file may not exist yet
      }
    }

    return {
      files: results.map(r => r.path),
      snippets,
      existingCode,
      totalFiles: this.index.documentCount
    };
  }

  watch(dir, callback, interval = 3000) {
    const lastModified = new Map();

    setInterval(() => {
      try {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isFile() && this.isCodeFile(entry.name)) {
            const fullPath = path.join(dir, entry.name);
            const stat = fs.statSync(fullPath);
            const prev = lastModified.get(fullPath);

            if (!prev || stat.mtimeMs > prev) {
              lastModified.set(fullPath, stat.mtimeMs);
              callback(fullPath, 'changed');
            }
          }
        }
      } catch {
        // ignore watch errors
      }
    }, interval);
  }
}

module.exports = { ContextScanner };
