// tests/benchmark.js - Pipeline validation without requiring a real model
const fs = require('fs');
const { ARC_PROMPTS, LANGUAGES } = require('../core/prompts');
const { ContextScanner } = require('../core/context');
const { ProjectManager } = require('../core/project');

async function runTests() {
  console.log('🧪 Cursor OSS v2 — Pipeline Benchmark\n');
  console.log('═'.repeat(50));

  let passed = 0;
  let total = 0;

  function test(name, fn) {
    total++;
    try {
      const result = fn();
      if (result && typeof result.then === 'function') {
        return result.then(() => {
          passed++;
          console.log(`✅ ${name}`);
        }).catch(err => {
          console.log(`❌ ${name}: ${err.message}`);
        });
      }
      passed++;
      console.log(`✅ ${name}`);
      return Promise.resolve();
    } catch (err) {
      console.log(`❌ ${name}: ${err.message}`);
      return Promise.resolve();
    }
  }

  const stages = ['analysis', 'requirements', 'code', 'review', 'refine', 'ideaToProject'];
  await test('All ARC prompt stages exist', () => {
    for (const stage of stages) {
      if (!ARC_PROMPTS[stage]?.system || !ARC_PROMPTS[stage]?.user) {
        throw new Error(`Missing prompt stage: ${stage}`);
      }
    }
  });

  await test('Language support defined', () => {
    if (Object.keys(LANGUAGES).length < 5) throw new Error('Expected 5+ languages');
  });

  const simulatedRequest = 'Add error handling to processData()';
  function hasUnresolvedPlaceholders(prompt) {
    return /\{(request|openFiles|recentEdits|task|analysis|context|plan|existing|original|proposed|code|issues|idea)\}/.test(prompt);
  }

  await test('Analysis template accepts variables', () => {
    const prompt = ARC_PROMPTS.analysis.user
      .replace('{request}', simulatedRequest)
      .replace('{openFiles}', 'app.js')
      .replace('{recentEdits}', 'modified processData');
    if (hasUnresolvedPlaceholders(prompt)) throw new Error('Unresolved placeholders');
  });

  await test('Requirements template accepts variables', () => {
    const prompt = ARC_PROMPTS.requirements.user
      .replace('{task}', simulatedRequest)
      .replace('{analysis}', '{"requestType":"feature"}')
      .replace('{context}', 'function processData() {}');
    if (hasUnresolvedPlaceholders(prompt)) throw new Error('Unresolved placeholders');
  });

  await test('Code template accepts variables', () => {
    const prompt = ARC_PROMPTS.code.user
      .replace('{plan}', '{"steps":[]}')
      .replace('{existing}', 'function processData() {}');
    if (hasUnresolvedPlaceholders(prompt)) throw new Error('Unresolved placeholders');
  });

  await test('Review template accepts variables', () => {
    const prompt = ARC_PROMPTS.review.user
      .replace('{original}', '{"code":"old"}')
      .replace('{proposed}', '{"files":[]}')
      .replace('{plan}', '{"steps":[]}');
    if (hasUnresolvedPlaceholders(prompt)) throw new Error('Unresolved placeholders');
  });

  await test('ContextScanner indexes project files', async () => {
    const scanner = new ContextScanner();
    const result = await scanner.scan('agent prompts', { rootDir: '.' });
    if (result.totalFiles < 1) throw new Error('No files indexed');
  });

  await test('ProjectManager save/load roundtrip', () => {
    const pm = new ProjectManager('.cursor-oss-test-projects');
    pm.save('test-project', { files: { 'app.js': 'console.log(1)' }, idea: 'test' });
    const loaded = pm.load('test-project');
    if (!loaded || loaded.idea !== 'test') throw new Error('Load failed');
    pm.delete('test-project');
    fs.rmSync('.cursor-oss-test-projects', { recursive: true, force: true });
  });

  function extractJSON(text) {
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if (start === -1 || end === -1) return null;
    try {
      return JSON.parse(text.substring(start, end + 1));
    } catch {
      const cleaned = text.substring(start, end + 1)
        .replace(/,\s*}/g, '}')
        .replace(/,\s*]/g, ']');
      return JSON.parse(cleaned);
    }
  }

  await test('extractJSON handles trailing commas', () => {
    const result = extractJSON('Here is JSON: {"score": 0.9, "passed": true,}');
    if (!result || result.score !== 0.9) throw new Error('Parse failed');
  });

  console.log('\n' + '═'.repeat(50));
  console.log(`📊 Results: ${passed}/${total} passed (${((passed / total) * 100).toFixed(0)}%)`);
  console.log('\nReady for real model inference.');
  console.log('Run: bash installer.sh && node server/inference.js');

  process.exit(passed === total ? 0 : 1);
}

runTests();
