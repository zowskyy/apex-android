// ui/vscode-bridge.js - Optional VS Code/Cursor integration
const path = require('path');

let vscode;
try {
  vscode = require('vscode');
} catch {
  vscode = null;
}

const { ARCAgent } = require('../core/agent');

class VSCodeBridge {
  constructor() {
    this.agent = null;
    this.outputChannel = null;
    this.statusBarItem = null;
    this.isProcessing = false;
  }

  async activate(context) {
    if (!vscode) {
      throw new Error('vscode module not available — run inside VS Code/Cursor');
    }

    console.log('🚀 Activating Cursor OSS (Free Coding Agent)');

    const config = vscode.workspace.getConfiguration('cursorOss');
    this.agent = new ARCAgent({
      inferenceUrl: config.get('inferenceUrl') || 'http://localhost:8899',
      maxReviewLoops: config.get('maxReviewLoops') || 2,
      qualityThreshold: config.get('qualityThreshold') || 0.80
    });

    this.outputChannel = vscode.window.createOutputChannel('Cursor OSS - ARC Cycle');
    this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    this.statusBarItem.text = '$(check) ARC Agent Ready';
    this.statusBarItem.show();
    context.subscriptions.push(this.statusBarItem);

    this.registerCommands(context);
    vscode.window.showInformationMessage('✅ Cursor OSS Agent ready — start server: node server/inference.js');
  }

  registerCommands(context) {
    context.subscriptions.push(
      vscode.commands.registerCommand('cursorOss.arcCycle', () => this.runARCCycle()),
      vscode.commands.registerCommand('cursorOss.showReview', () => this.showReviewPanel()),
      vscode.commands.registerCommand('cursorOss.toggleOffline', () => this.toggleOfflineMode())
    );
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

    const request = await vscode.window.showInputBox({
      prompt: 'What do you want to do?',
      placeHolder: 'Describe your coding task...',
      ignoreFocusOut: true
    });

    if (!request) {
      this.isProcessing = false;
      this.statusBarItem.text = '$(check) ARC Agent Ready';
      return;
    }

    this.outputChannel.show();
    this.outputChannel.appendLine(`\nREQUEST: ${request}\n`);

    try {
      const result = await this.agent.process(request, {
        currentFile: editor.document.uri.fsPath,
        edits: []
      });

      if (result.success) {
        this.displayResults(result);
        await this.applyFiles(result.code?.files || [], editor);
      } else {
        this.outputChannel.appendLine(`❌ ERROR: ${result.error}`);
        vscode.window.showErrorMessage(`ARC cycle failed: ${result.error}`);
      }
    } catch (err) {
      this.outputChannel.appendLine(`❌ FATAL: ${err.message}`);
      vscode.window.showErrorMessage(`Agent error: ${err.message}`);
    } finally {
      this.isProcessing = false;
      this.statusBarItem.text = '$(check) ARC Agent Ready';
    }
  }

  displayResults(result) {
    this.outputChannel.appendLine('📊 ANALYSIS:');
    this.outputChannel.appendLine(JSON.stringify(result.analysis, null, 2));
    this.outputChannel.appendLine('\n📋 PLAN:');
    if (result.plan?.steps) {
      result.plan.steps.forEach(step => {
        this.outputChannel.appendLine(`  ${step.step}. ${step.description}`);
      });
    }
    this.outputChannel.appendLine('\n💻 CODE:');
    if (result.code?.files) {
      result.code.files.forEach(file => {
        this.outputChannel.appendLine(`\n  ${file.path}`);
        this.outputChannel.appendLine(file.content);
      });
    }
    this.outputChannel.appendLine(`\n🔍 REVIEW: ${result.review?.score ?? 'N/A'}`);
    this.outputChannel.appendLine(`⏱️  ${result.elapsed}ms | 🔄 ${result.loops} loops`);
  }

  async applyFiles(files, editor) {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder || files.length === 0) return;

    const edit = new vscode.WorkspaceEdit();
    for (const file of files) {
      const targetPath = path.isAbsolute(file.path)
        ? file.path
        : path.join(workspaceFolder.uri.fsPath, file.path);
      const uri = vscode.Uri.file(targetPath);
      edit.createFile(uri, { overwrite: true, ignoreIfExists: false });
      edit.insert(uri, new vscode.Position(0, 0), file.content);
    }
    await vscode.workspace.applyEdit(edit);
    vscode.window.showInformationMessage('✅ Code changes applied');
  }

  showReviewPanel() {
    const stats = this.agent?.getStats() || { requests: 0, avgLoops: 0, avgTime: 0 };
    const panel = vscode.window.createWebviewPanel(
      'arcReview', 'ARC Review Cycle', vscode.ViewColumn.Beside, { enableScripts: true }
    );
    panel.webview.html = `<!DOCTYPE html><html><body style="font-family:monospace;padding:20px;background:#1e1e1e;color:#d4d4d4">
      <h1>🔍 ARC Review Cycle</h1>
      <p>Requests: ${stats.requests}</p>
      <p>Avg loops: ${stats.avgLoops.toFixed(1)}</p>
      <p>Avg time: ${Math.round(stats.avgTime)}ms</p>
      <p style="color:#6a9955">✅ Offline — no subscription needed</p>
    </body></html>`;
  }

  async toggleOfflineMode() {
    const config = vscode.workspace.getConfiguration('cursorOss');
    const current = config.get('offlineMode') ?? true;
    await config.update('offlineMode', !current, true);
    vscode.window.showInformationMessage(`Offline mode: ${!current ? 'ON' : 'OFF'}`);
  }

  async deactivate() {
    console.log('👋 Cursor OSS deactivated');
  }
}

let bridgeInstance = null;

async function activate(context) {
  bridgeInstance = new VSCodeBridge();
  await bridgeInstance.activate(context);
  context.subscriptions.push({ dispose: () => bridgeInstance?.deactivate() });
}

async function deactivate() {
  if (bridgeInstance) {
    await bridgeInstance.deactivate();
    bridgeInstance = null;
  }
}

module.exports = { activate, deactivate, VSCodeBridge };
