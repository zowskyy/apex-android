// ide-bridge.js - Bridges ARC Agent to IDE (VSCode/Cursor compatible)
const vscode = require('vscode');
const { ARCAgent } = require('./arc-agent');
const path = require('path');

class IDEBridge {
  constructor() {
    this.agent = null;
    this.outputChannel = null;
    this.statusBarItem = null;
    this.isProcessing = false;
  }

  async activate(context) {
    console.log('🚀 Activating Cursor OSS (Free Coding Agent)');
    
    // Initialize ARC Agent
    const config = vscode.workspace.getConfiguration('cursorOss');
    this.agent = new ARCAgent({
      modelPath: config.get('modelPath') || path.join(context.extensionPath, 'models', 'codeqwen-7b-q4.gguf'),
      maxReviewLoops: config.get('maxReviewLoops') || 3,
      qualityThreshold: config.get('qualityThreshold') || 0.85
    });

    await this.agent.initialize();

    // Setup UI
    this.outputChannel = vscode.window.createOutputChannel('Cursor OSS - ARC Cycle');
    this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    this.statusBarItem.text = '$(sync~spin) ARC Agent Ready';
    this.statusBarItem.show();
    context.subscriptions.push(this.statusBarItem);

    // Register commands
    this.registerCommands(context);
    
    // Register completion provider
    this.registerCompletionProvider(context);
    
    // Watch for file changes to update context
    this.watchFileChanges(context);

    vscode.window.showInformationMessage('✅ Cursor OSS Agent ready - No subscription needed!');
  }

  registerCommands(context) {
    // Command: Full ARC cycle on selection
    const arcCycleCommand = vscode.commands.registerCommand('cursorOss.arcCycle', async () => {
      await this.runARCCycle();
    });
    
    // Command: Quick completion
    const quickCompleteCommand = vscode.commands.registerCommand('cursorOss.quickComplete', async () => {
      await this.runQuickCompletion();
    });

    // Command: Show ARC review panel
    const showReviewCommand = vscode.commands.registerCommand('cursorOss.showReview', async () => {
      await this.showReviewPanel();
    });

    // Command: Toggle offline mode
    const offlineModeCommand = vscode.commands.registerCommand('cursorOss.toggleOffline', async () => {
      await this.toggleOfflineMode();
    });

    context.subscriptions.push(
      arcCycleCommand, 
      quickCompleteCommand, 
      showReviewCommand,
      offlineModeCommand
    );
  }

  registerCompletionProvider(context) {
    const provider = vscode.languages.registerInlineCompletionItemProvider(
      { pattern: '**' }, // All files
      {
        provideInlineCompletionItems: async (document, position) => {
          if (this.isProcessing) return [];
          
          const linePrefix = document.lineAt(position).text.substring(0, position.character);
          if (linePrefix.trim().length < 3) return []; // Don't suggest for short prefixes

          try {
            const result = await this.agent.processRequest(
              `Complete the code after: ${linePrefix}`,
              {
                currentFile: document.uri.fsPath,
                openFiles: [document.uri.fsPath],
                recentEdits: []
              }
            );

            if (result.success && result.code?.patches?.[0]?.diff) {
              const completionText = this.extractCompletionFromDiff(result.code.patches[0].diff);
              if (completionText) {
                return [new vscode.InlineCompletionItem(completionText)];
              }
            }
          } catch (err) {
            // Silent fail for completions
          }
          
          return [];
        }
      }
    );

    context.subscriptions.push(provider);
  }

  async runARCCycle() {
    if (this.isProcessing) {
      vscode.window.showWarningMessage('ARC cycle already in progress...');
      return;
    }

    this.isProcessing = true;
    this.statusBarItem.text = '$(loading~spin) ARC Cycle Running...';

    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showErrorMessage('No active editor');
      this.isProcessing = false;
      return;
    }

    // Get user request
    const request = await vscode.window.showInputBox({
      prompt: 'What do you want to do? (e.g., "Add error handling", "Refactor this function", "Fix the bug on line 42")',
      placeHolder: 'Describe your coding task...',
      ignoreFocusOut: true
    });

    if (!request) {
      this.isProcessing = false;
      this.statusBarItem.text = '$(check) ARC Agent Ready';
      return;
    }

    this.outputChannel.show();
    this.outputChannel.appendLine(`\n${'='.repeat(60)}`);
    this.outputChannel.appendLine(`REQUEST: ${request}`);
    this.outputChannel.appendLine(`${'='.repeat(60)}\n`);

    try {
      const selection = editor.selection;
      const selectedText = editor.document.getText(selection);
      
      const result = await this.agent.processRequest(request, {
        currentFile: editor.document.uri.fsPath,
        selectedText: selectedText || undefined,
        openFiles: [editor.document.uri.fsPath],
        recentEdits: []
      });

      if (result.success) {
        this.displayARCResults(result);
        
        // Apply patches if available
        if (result.code?.patches) {
          await this.applyPatches(result.code.patches, editor);
        }
      } else {
        this.outputChannel.appendLine(`\n❌ ERROR: ${result.error}`);
        vscode.window.showErrorMessage(`ARC cycle failed: ${result.error}`);
      }
    } catch (err) {
      this.outputChannel.appendLine(`\n❌ FATAL: ${err.message}`);
      vscode.window.showErrorMessage(`Agent error: ${err.message}`);
    } finally {
      this.isProcessing = false;
      this.statusBarItem.text = '$(check) ARC Agent Ready';
    }
  }

  displayARCResults(result) {
    this.outputChannel.appendLine('\n📊 ANALYSIS:');
    this.outputChannel.appendLine(JSON.stringify(result.analysis, null, 2));
    
    this.outputChannel.appendLine('\n📋 PLAN:');
    if (result.plan?.plan) {
      result.plan.plan.forEach(step => {
        this.outputChannel.appendLine(`  ${step.step}. [${step.action}] ${step.description}`);
      });
    }
    
    this.outputChannel.appendLine('\n💻 CODE CHANGES:');
    if (result.code?.patches) {
      result.code.patches.forEach(patch => {
        this.outputChannel.appendLine(`\n  File: ${patch.file}`);
        this.outputChannel.appendLine(patch.diff);
      });
    }
    
    this.outputChannel.appendLine(`\n🔍 REVIEW: Score ${result.review?.score || 'N/A'}`);
    if (result.review?.issues?.length > 0) {
      this.outputChannel.appendLine('Issues found:');
      result.review.issues.forEach(issue => {
        this.outputChannel.appendLine(`  [${issue.severity}] ${issue.description}`);
      });
    }
    
    this.outputChannel.appendLine(`\n⏱️  Total latency: ${result.latency}ms`);
    this.outputChannel.appendLine(`🔄 Refinement loops: ${result.refinements}`);
  }

  async applyPatches(patches, editor) {
    const document = editor.document;
    
    for (const patch of patches) {
      if (patch.file === document.uri.fsPath || !patch.file) {
        // Parse and apply diff
        const edits = this.parseDiffToEdits(patch.diff, document);
        
        if (edits.length > 0) {
          const edit = new vscode.WorkspaceEdit();
          edits.forEach(e => edit.replace(document.uri, e.range, e.newText));
          await vscode.workspace.applyEdit(edit);
        }
      }
    }
    
    vscode.window.showInformationMessage('✅ Code changes applied (review in ARC panel)');
  }

  parseDiffToEdits(diff, document) {
    const edits = [];
    const lines = diff.split('\n');
    let currentHunk = null;
    
    for (const line of lines) {
      if (line.startsWith('@@')) {
        // Parse hunk header: @@ -oldStart,oldCount +newStart,newCount @@
        const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
        if (match) {
          currentHunk = {
            oldLine: parseInt(match[1]) - 1, // 0-based
            newLine: parseInt(match[2]) - 1,
            removedLines: [],
            addedLines: []
          };
        }
      } else if (currentHunk) {
        if (line.startsWith('-')) {
          currentHunk.removedLines.push(line.substring(1));
        } else if (line.startsWith('+')) {
          currentHunk.addedLines.push(line.substring(1));
        } else if (line.startsWith(' ') || line === '') {
          // Context line - flush current changes
          if (currentHunk.removedLines.length > 0 || currentHunk.addedLines.length > 0) {
            const range = new vscode.Range(
              currentHunk.oldLine, 0,
              currentHunk.oldLine + currentHunk.removedLines.length, 0
            );
            edits.push({
              range,
              newText: currentHunk.addedLines.join('\n')
            });
            currentHunk.oldLine += currentHunk.removedLines.length;
            currentHunk.removedLines = [];
            currentHunk.addedLines = [];
          }
          currentHunk.oldLine++;
        }
      }
    }
    
    return edits;
  }

  extractCompletionFromDiff(diff) {
    const lines = diff.split('\n');
    const addedLines = lines
      .filter(line => line.startsWith('+'))
      .map(line => line.substring(1));
    return addedLines.join('\n');
  }

  async runQuickCompletion() {
    // Triggered by hotkey - gets completion without full ARC cycle
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const position = editor.selection.active;
    const linePrefix = editor.document.lineAt(position).text.substring(0, position.character);
    
    // Quick single-pass generation (skip review for speed)
    // Implementation similar to completion provider but on-demand
  }

  async showReviewPanel() {
    // Show the last ARC cycle results in a webview panel
    const panel = vscode.window.createWebviewPanel(
      'arcReview',
      'ARC Review Cycle',
      vscode.ViewColumn.Beside,
      { enableScripts: true }
    );

    panel.webview.html = this.generateReviewHTML();
  }

  generateReviewHTML() {
    const telemetry = this.agent.getTelemetry();
    
    return `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: monospace; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
    .stage { margin: 10px 0; padding: 10px; background: #2d2d2d; border-radius: 5px; }
    .stage-title { color: #569cd6; font-weight: bold; }
    .pass { color: #6a9955; }
    .fail { color: #f44747; }
    .metric { display: inline-block; margin: 10px; padding: 15px; background: #3c3c3c; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 24px; color: #4ec9b0; }
  </style>
</head>
<body>
  <h1>🔍 ARC Review Cycle</h1>
  
  <div class="metrics">
    <div class="metric">
      <div>Requests</div>
      <div class="metric-value">${telemetry.requestsProcessed}</div>
    </div>
    <div class="metric">
      <div>Avg Review Loops</div>
      <div class="metric-value">${telemetry.avgReviewLoops.toFixed(1)}</div>
    </div>
    <div class="metric">
      <div>Avg Latency</div>
      <div class="metric-value">${Math.round(telemetry.avgLatencyMs)}ms</div>
    </div>
  </div>

  <div class="stage">
    <div class="stage-title">📊 Analysis Stage</div>
    <div>Understands intent and gathers context</div>
  </div>
  
  <div class="stage">
    <div class="stage-title">📋 Requirements Stage</div>
    <div>Creates implementation plan before coding</div>
  </div>
  
  <div class="stage">
    <div class="stage-title">💻 Code Generation Stage</div>
    <div>Generates code following the plan</div>
  </div>
  
  <div class="stage">
    <div class="stage-title">🔍 Review Stage</div>
    <div>Self-critiques and refines until quality threshold met</div>
  </div>

  <p style="margin-top: 20px; color: #6a9955;">
    ✅ Running entirely offline - No subscription needed
  </p>
</body>
</html>`;
  }

  watchFileChanges(context) {
    const watcher = vscode.workspace.createFileSystemWatcher('**/*');
    
    watcher.onDidChange(async (uri) => {
      // Update context index when files change
      if (this.agent?.contextGatherer) {
        // Re-index changed file
      }
    });
    
    context.subscriptions.push(watcher);
  }

  async toggleOfflineMode() {
    const config = vscode.workspace.getConfiguration('cursorOss');
    const currentMode = config.get('offlineMode') || false;
    await config.update('offlineMode', !currentMode, true);
    vscode.window.showInformationMessage(
      `Offline mode: ${!currentMode ? 'ON' : 'OFF'} (no internet required)`
    );
  }

  async deactivate() {
    if (this.agent) {
      await this.agent.shutdown();
    }
    console.log('👋 Cursor OSS deactivated');
  }
}

module.exports = { IDEBridge };
