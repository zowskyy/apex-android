// context-gatherer.js - Lightweight codebase context retrieval
const fs = require('fs').promises;
const path = require('path');
const MiniSearch = require('minisearch');

class ContextGatherer {
  constructor(config = {}) {
    this.config = {
      maxFiles: config.maxFiles || 50,
      maxSnippets: config.maxSnippets || 5,
      snippetSize: config.snippetSize || 2000, // characters
      watchDirs: config.watchDirs || ['./'],
      excludePatterns: config.excludePatterns || [
        'node_modules', '.git', 'dist', 'build', 
        '*.min.js', '*.bundle.js', 'package-lock.json'
      ],
      ...config
    };
    
    this.searchIndex = null;
    this.fileCache = new Map();
    this.isInitialized = false;
  }

  async initialize() {
    console.log('📚 Building codebase index...');
    this.searchIndex = new MiniSearch({
      fields: ['content', 'path', 'symbols'],
      storeFields: ['path', 'symbols'],
      searchOptions: {
        boost: { path: 2, symbols: 3 },
        fuzzy: 0.2
      }
    });

    await this.indexDirectory(process.cwd());
    this.isInitialized = true;
    console.log(`✅ Indexed ${this.searchIndex.documentCount} files`);
  }

  async indexDirectory(dirPath) {
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (this.shouldExclude(fullPath)) continue;
        
        if (entry.isDirectory()) {
          await this.indexDirectory(fullPath);
        } else if (this.isCodeFile(entry.name)) {
          await this.indexFile(fullPath);
        }
      }
    } catch (err) {
      // Skip directories we can't read
    }
  }

  shouldExclude(filePath) {
    return this.config.excludePatterns.some(pattern => {
      if (pattern.startsWith('*.')) {
        return filePath.endsWith(pattern.slice(1));
      }
      return filePath.includes(pattern);
    });
  }

  isCodeFile(filename) {
    const codeExtensions = ['.js', '.ts', '.jsx', '.tsx', '.py', '.rs', '.go', '.java', '.cpp', '.c', '.h'];
    return codeExtensions.some(ext => filename.endsWith(ext));
  }

  async indexFile(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const symbols = this.extractSymbols(content, filePath);
      
      const doc = {
        id: filePath,
        path: filePath,
        content: content.substring(0, 10000), // First 10k chars for indexing
        symbols: symbols.join(' ')
      };

      this.searchIndex.add(doc);
      this.fileCache.set(filePath, { content, symbols });
    } catch (err) {
      // Skip unreadable files
    }
  }

  extractSymbols(content, filePath) {
    const symbols = [];
    const ext = path.extname(filePath);
    
    // Extract function and class names
    if (['.js', '.ts', '.jsx', '.tsx'].includes(ext)) {
      const funcRegex = /(?:function|const|let|var)\s+(\w+)/g;
      const classRegex = /class\s+(\w+)/g;
      let match;
      while ((match = funcRegex.exec(content)) !== null) symbols.push(match[1]);
      while ((match = classRegex.exec(content)) !== null) symbols.push(match[1]);
    } else if (ext === '.py') {
      const funcRegex = /def\s+(\w+)/g;
      const classRegex = /class\s+(\w+)/g;
      let match;
      while ((match = funcRegex.exec(content)) !== null) symbols.push(match[1]);
      while ((match = classRegex.exec(content)) !== null) symbols.push(match[1]);
    }
    
    return symbols;
  }

  async gather(request, context = {}) {
    if (!this.isInitialized) await this.initialize();

    // Search for relevant files
    const searchResults = this.searchIndex.search(request, { 
      prefix: true,
      fuzzy: 0.2,
      max: this.config.maxSnippets 
    });

    const snippets = [];
    const relevantFiles = new Set(context.openFiles || []);

    for (const result of searchResults) {
      relevantFiles.add(result.path);
      
      // Get relevant snippet from cached content
      const cached = this.fileCache.get(result.path);
      if (cached) {
        const snippet = this.extractRelevantSnippet(cached.content, request);
        snippets.push(`// ${result.path}\n${snippet}`);
      }
    }

    // Get full content for files mentioned in context
    let existingCode = '';
    if (context.currentFile) {
      try {
        existingCode = await fs.readFile(context.currentFile, 'utf-8');
      } catch (err) {
        // File might not exist yet
      }
    }

    return {
      snippets: snippets.slice(0, this.config.maxSnippets),
      openFiles: [...relevantFiles],
      recentEdits: context.recentEdits || [],
      existingCode
    };
  }

  extractRelevantSnippet(content, query) {
    const lines = content.split('\n');
    const queryWords = query.toLowerCase().split(/\s+/);
    
    // Find lines that match query words
    const scoredLines = lines.map((line, index) => {
      const lowerLine = line.toLowerCase();
      let score = 0;
      for (const word of queryWords) {
        if (lowerLine.includes(word)) score++;
      }
      return { line, index, score };
    });

    // Get context around highest scoring lines
    const bestLine = scoredLines.reduce((best, current) => 
      current.score > best.score ? current : best, { score: -1 });

    if (bestLine.score > 0) {
      const start = Math.max(0, bestLine.index - 10);
      const end = Math.min(lines.length, bestLine.index + 10);
      return lines.slice(start, end).join('\n');
    }

    // Fallback: return first portion
    return lines.slice(0, 20).join('\n');
  }

  async cleanup() {
    this.searchIndex = null;
    this.fileCache.clear();
  }
}

module.exports = { ContextGatherer };
