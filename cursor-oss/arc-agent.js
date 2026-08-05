// arc-agent.js - The self-reviewing coding agent
const { ARC_PROMPTS } = require('./prompts');
const { ModelLoader } = require('./model-loader');
const { ContextGatherer } = require('./context-gatherer');
const fs = require('fs');
const path = require('path');

class ARCAgent {
  constructor(config = {}) {
    this.config = {
      maxReviewLoops: config.maxReviewLoops || 3,
      qualityThreshold: config.qualityThreshold || 0.85,
      modelPath: config.modelPath || './models/codeqwen-7b-q4.gguf',
      contextWindow: config.contextWindow || 8192,
      temperature: config.temperature || 0.1,
      ...config
    };

    this.model = null;
    this.contextGatherer = new ContextGatherer();
    this.conversationHistory = [];
    this.telemetry = {
      requestsProcessed: 0,
      avgReviewLoops: 0,
      successRate: 0,
      avgLatencyMs: 0
    };
  }

  async initialize() {
    console.log('🔧 Initializing ARC Agent...');
    this.model = await ModelLoader.load(this.config.modelPath, {
      contextSize: this.config.contextWindow,
      threads: Math.max(1, require('os').cpus().length - 1), // Leave one core free
      batchSize: 512
    });
    await this.contextGatherer.initialize();
    console.log('✅ ARC Agent ready (offline, local, free)');
  }

  // Generate text using local model
  async generate(prompt, systemPrompt, format = 'json') {
    const startTime = Date.now();
    const IM_END = '<|' + 'im_end' + '|>';
    
    const fullPrompt = `<|im_start|>system\n${systemPrompt}${IM_END}\n<|im_start|>user\n${prompt}${IM_END}\n<|im_start|>assistant\n`;
    
    const response = await this.model.generate(fullPrompt, {
      temperature: this.config.temperature,
      topP: 0.95,
      maxTokens: 2048,
      stop: [IM_END, '<|im_start|>']
    });

    const latency = Date.now() - startTime;
    this.telemetry.avgLatencyMs = 
      (this.telemetry.avgLatencyMs * this.telemetry.requestsProcessed + latency) / 
      (this.telemetry.requestsProcessed + 1);

    // Extract JSON from response
    try {
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch && format === 'json') {
        return { parsed: JSON.parse(jsonMatch[0]), raw: response, latency };
      }
      return { parsed: response, raw: response, latency };
    } catch (e) {
      return { parsed: response, raw: response, latency, parseError: e.message };
    }
  }

  // STAGE 1: ANALYSIS
  async analyze(request, context) {
    console.log('📊 ARC Stage 1/4: Analysis');
    
    const prompt = ARC_PROMPTS.analysis.userTemplate
      .replace('{request}', request)
      .replace('{openFiles}', context.openFiles.join('\n'))
      .replace('{recentEdits}', context.recentEdits.join('\n'));

    const result = await this.generate(prompt, ARC_PROMPTS.analysis.system);
    
    if (result.parseError) {
      // Fallback: extract what we can
      return {
        requestType: 'completion',
        language: 'unknown',
        files: context.openFiles,
        symbols: [],
        constraints: [],
        ambiguities: null,
        complexity: 'moderate'
      };
    }

    this.conversationHistory.push({ stage: 'analysis', result: result.parsed });
    return result.parsed;
  }

  // STAGE 2: REQUIREMENTS (PLANNING)
  async plan(taskDescription, analysis, contextSnippets) {
    console.log('📋 ARC Stage 2/4: Planning');
    
    const prompt = ARC_PROMPTS.requirements.userTemplate
      .replace('{taskDescription}', taskDescription)
      .replace('{analysisJson}', JSON.stringify(analysis, null, 2))
      .replace('{contextSnippets}', contextSnippets.join('\n---\n'));

    const result = await this.generate(prompt, ARC_PROMPTS.requirements.system);
    
    this.conversationHistory.push({ stage: 'requirements', result: result.parsed });
    return result.parsed || { plan: [], fallbackStrategy: 'manual_review' };
  }

  // STAGE 3: CODE GENERATION
  async generateCode(plan, existingCode) {
    console.log('💻 ARC Stage 3/4: Code Generation');
    
    const prompt = ARC_PROMPTS.code.userTemplate
      .replace('{planJson}', JSON.stringify(plan, null, 2))
      .replace('{existingCode}', typeof existingCode === 'string' ? existingCode : JSON.stringify(existingCode, null, 2));

    const result = await this.generate(prompt, ARC_PROMPTS.code.system);
    
    this.conversationHistory.push({ stage: 'code', result: result.parsed });
    return result.parsed || { patches: [] };
  }

  // STAGE 4: REVIEW
  async review(originalCode, proposedChanges, plan) {
    console.log('🔍 ARC Stage 4/4: Review');
    
    const prompt = ARC_PROMPTS.review.userTemplate
      .replace('{originalCode}', typeof originalCode === 'string' ? originalCode : JSON.stringify(originalCode, null, 2))
      .replace('{proposedChanges}', JSON.stringify(proposedChanges, null, 2))
      .replace('{planJson}', JSON.stringify(plan, null, 2));

    const result = await this.generate(prompt, ARC_PROMPTS.review.system);
    
    this.conversationHistory.push({ stage: 'review', result: result.parsed });
    return result.parsed || { score: 0, passed: false, issues: [] };
  }

  // REFINE: Fix issues found in review
  async refine(originalProposal, reviewIssues, plan) {
    console.log('🔧 Refining code based on review...');
    
    const prompt = ARC_PROMPTS.refine.userTemplate
      .replace('{originalProposal}', JSON.stringify(originalProposal, null, 2))
      .replace('{reviewIssues}', JSON.stringify(reviewIssues, null, 2))
      .replace('{planJson}', JSON.stringify(plan, null, 2));

    const result = await this.generate(prompt, ARC_PROMPTS.refine.system);
    return result.parsed || originalProposal;
  }

  // FULL ARC CYCLE
  async processRequest(request, context = {}) {
    const startTime = Date.now();
    this.conversationHistory = [];
    
    console.log(`\n🚀 Processing: "${request.substring(0, 100)}${request.length > 100 ? '...' : ''}"`);
    console.log('═'.repeat(60));

    try {
      // Gather context from codebase
      const gatheredContext = await this.contextGatherer.gather(request, context);
      
      // STAGE 1: Analysis
      const analysis = await this.analyze(request, {
        openFiles: context.openFiles || gatheredContext.openFiles || [],
        recentEdits: context.recentEdits || gatheredContext.recentEdits || []
      });

      // STAGE 2: Plan
      const plan = await this.plan(request, analysis, gatheredContext.snippets || []);

      // STAGE 3: Generate initial code
      let currentCode = await this.generateCode(plan, gatheredContext.existingCode || '');

      // STAGE 4 + REFINE LOOP: Review and improve
      let reviewResult;
      let loopCount = 0;

      do {
        reviewResult = await this.review(
          gatheredContext.existingCode || '', 
          currentCode, 
          plan
        );

        if (!reviewResult.passed && reviewResult.score < this.config.qualityThreshold) {
          console.log(`   ⚠️  Review score: ${reviewResult.score} (threshold: ${this.config.qualityThreshold})`);
          console.log(`   Issues found: ${reviewResult.issues?.length || 0}`);
          
          if (loopCount < this.config.maxReviewLoops) {
            currentCode = await this.refine(currentCode, reviewResult.issues, plan);
            loopCount++;
            console.log(`   🔄 Refinement loop ${loopCount}/${this.config.maxReviewLoops}`);
          } else {
            console.log(`   ⚠️  Max refinement loops (${this.config.maxReviewLoops}) reached`);
            break;
          }
        } else {
          console.log(`   ✅ Review passed! Score: ${reviewResult.score}`);
          break;
        }
      } while (!reviewResult.passed && loopCount < this.config.maxReviewLoops);

      // Update telemetry
      this.telemetry.requestsProcessed++;
      this.telemetry.avgReviewLoops = 
        (this.telemetry.avgReviewLoops * (this.telemetry.requestsProcessed - 1) + loopCount) / 
        this.telemetry.requestsProcessed;
      
      const totalLatency = Date.now() - startTime;

      console.log(`⏱️  Total time: ${totalLatency}ms | Review loops: ${loopCount}`);
      console.log('═'.repeat(60));

      return {
        success: true,
        analysis,
        plan,
        code: currentCode,
        review: reviewResult,
        refinements: loopCount,
        latency: totalLatency,
        conversationHistory: this.conversationHistory
      };

    } catch (error) {
      console.error('❌ ARC Cycle Error:', error);
      return {
        success: false,
        error: error.message,
        conversationHistory: this.conversationHistory
      };
    }
  }

  // Get telemetry for monitoring
  getTelemetry() {
    return { ...this.telemetry };
  }

  // Shutdown gracefully
  async shutdown() {
    console.log('🛑 Shutting down ARC Agent...');
    await this.contextGatherer.cleanup();
    // Model cleanup handled by node-llama-cpp
    console.log('👋 Agent stopped');
  }
}

// CLI entry point when run directly
if (require.main === module) {
  const request = process.argv.slice(2).join(' ') || 'Write a hello world function in JavaScript';
  const agent = new ARCAgent();
  agent.initialize()
    .then(() => agent.processRequest(request))
    .then((result) => {
      console.log('\nResult:', JSON.stringify(result, null, 2));
      return agent.shutdown();
    })
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}

module.exports = { ARCAgent };
