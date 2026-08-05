#!/usr/bin/env node
// ui/cli.js - Command-line interface for headless systems
const readline = require('readline');
const { ARCAgent } = require('../core/agent');

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  dim: '\x1b[2m'
};

function color(text, c) {
  return `${COLORS[c]}${text}${COLORS.reset}`;
}

async function main() {
  console.log(color('\n⚡ Cursor OSS — Free Coding Agent', 'cyan'));
  console.log(color('Zero subscription. Runs offline. Built for everyone.\n', 'dim'));

  const args = process.argv.slice(2);
  const agent = new ARCAgent();

  if (args.length > 0 && args[0] !== 'idea') {
    const request = args.join(' ');
    console.log(color(`Request: ${request}\n`, 'yellow'));
    console.log(color('🔍 Starting ARC cycle...', 'blue'));

    const result = await agent.process(request);

    if (result.success) {
      console.log(color('\n✅ Complete!', 'green'));
      console.log(color(`⏱️  ${result.elapsed}ms | 🔄 ${result.loops} review loops\n`, 'dim'));

      if (result.code?.files) {
        for (const file of result.code.files) {
          console.log(color(`📁 ${file.path}`, 'cyan'));
          console.log(file.content);
          console.log('');
        }
      }
    } else {
      console.log(color(`❌ Error: ${result.error}`, 'red'));
    }

    process.exit(result.success ? 0 : 1);
  }

  if (args[0] === 'idea') {
    const idea = args.slice(1).join(' ') || 'a community app';
    console.log(color(`💡 Idea: ${idea}\n`, 'yellow'));
    try {
      const result = await agent.buildFromIdea(idea);
      console.log(color('Clarifying questions:', 'cyan'));
      result.clarifyingQuestions.forEach((q, i) => console.log(`  ${i + 1}. ${q}`));
      console.log(color(`\n${result.message}`, 'dim'));
    } catch (err) {
      console.log(color(`❌ ${err.message}`, 'red'));
      process.exit(1);
    }
    process.exit(0);
  }

  console.log(color('Type your request, "idea <description>", or "exit". Ctrl+C to quit.\n', 'dim'));

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: color('You > ', 'green')
  });

  rl.prompt();

  rl.on('line', async (line) => {
    const input = line.trim();

    if (!input) {
      rl.prompt();
      return;
    }

    if (input === 'exit' || input === 'quit') {
      console.log(color('\n👋 Goodbye!', 'cyan'));
      process.exit(0);
    }

    if (input.startsWith('idea')) {
      const idea = input.replace(/^idea\s*/i, '') || 'a community app';
      console.log(color('\n💡 Turning your idea into a project plan...\n', 'yellow'));
      try {
        const result = await agent.buildFromIdea(idea);
        result.clarifyingQuestions.forEach((q, i) => console.log(`  ${i + 1}. ${q}`));
        console.log(color(`\n${result.message}`, 'dim'));
      } catch (err) {
        console.log(color(`❌ ${err.message}`, 'red'));
      }
      console.log('');
      rl.prompt();
      return;
    }

    console.log(color('\n🔍 Starting ARC cycle...', 'blue'));

    try {
      const result = await agent.process(input);

      if (result.success) {
        console.log(color(`\n✅ Complete! (${result.elapsed}ms, ${result.loops} review loops)`, 'green'));

        if (result.plan?.steps) {
          console.log(color('\n📋 Plan:', 'yellow'));
          for (const step of result.plan.steps) {
            console.log(`  ${step.step}. ${step.description}`);
          }
        }

        if (result.code?.files) {
          console.log(color('\n📁 Generated Files:', 'cyan'));
          for (const file of result.code.files) {
            console.log(color(`\n── ${file.path} ──`, 'blue'));
            console.log(file.content);
          }
        }

        if (result.review?.score !== undefined) {
          console.log(color(`\n🔍 Review Score: ${result.review.score}/1.0`,
            result.review.score >= 0.8 ? 'green' : 'yellow'));
        }
      } else {
        console.log(color(`\n❌ Error: ${result.error}`, 'red'));
      }
    } catch (err) {
      console.log(color(`\n❌ ${err.message}`, 'red'));
    }

    console.log('');
    rl.prompt();
  });

  rl.on('close', () => {
    console.log(color('\n👋 Goodbye!', 'cyan'));
    process.exit(0);
  });
}

main().catch(err => {
  console.error(color(`Fatal: ${err.message}`, 'red'));
  process.exit(1);
});
