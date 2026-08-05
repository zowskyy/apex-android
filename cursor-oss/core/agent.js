// core/agent.js - The heart. Pure JavaScript. No native deps.
const { ARC_PROMPTS } = require('./prompts');
const { ContextScanner } = require('./context');
const { ProjectManager } = require('./project');

class ARCAgent {
  constructor(config = {}) {
    this.config = {
      maxReviewLoops: config.maxReviewLoops || 2,
      qualityThreshold: config.qualityThreshold || 0.80,
      temperature: config.temperature || 0.1,
      language: config.language || 'en',
      ...config
    };

    this.inferenceUrl = config.inferenceUrl || 'http://localhost:8899';
    this.scanner = new ContextScanner();
    this.projects = new ProjectManager(config.projectDir);
    this.history = [];
    this.stats = { requests: 0, avgLoops: 0, avgTime: 0 };
  }

  async ask(prompt, systemPrompt) {
    const response = await fetch(`${this.inferenceUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: prompt }
        ],
        temperature: this.config.temperature,
        max_tokens: 2048
      })
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(`Inference failed (${response.status}): ${err}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  extractJSON(text) {
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if (start === -1 || end === -1) return null;

    try {
      return JSON.parse(text.substring(start, end + 1));
    } catch {
      const cleaned = text.substring(start, end + 1)
        .replace(/,\s*}/g, '}')
        .replace(/,\s*]/g, ']')
        .replace(/```json/g, '')
        .replace(/```/g, '');
      try {
        return JSON.parse(cleaned);
      } catch {
        return null;
      }
    }
  }

  async analyze(request, context) {
    const prompt = ARC_PROMPTS.analysis.user
      .replace('{request}', request)
      .replace('{openFiles}', (context.files || []).join('\n'))
      .replace('{recentEdits}', (context.edits || []).join('\n'));

    const response = await this.ask(prompt, ARC_PROMPTS.analysis.system);
    return this.extractJSON(response) || {
      requestType: 'unknown',
      complexity: 'moderate'
    };
  }

  async plan(task, analysis, snippets) {
    const prompt = ARC_PROMPTS.requirements.user
      .replace('{task}', task)
      .replace('{analysis}', JSON.stringify(analysis))
      .replace('{context}', snippets.join('\n---\n'));

    const response = await this.ask(prompt, ARC_PROMPTS.requirements.system);
    return this.extractJSON(response) || { steps: [] };
  }

  async generateCode(plan, existingCode) {
    const prompt = ARC_PROMPTS.code.user
      .replace('{plan}', JSON.stringify(plan))
      .replace('{existing}', typeof existingCode === 'string' ? existingCode : JSON.stringify(existingCode));

    const response = await this.ask(prompt, ARC_PROMPTS.code.system);
    return this.extractJSON(response) || { files: [] };
  }

  async review(original, proposed, plan) {
    const prompt = ARC_PROMPTS.review.user
      .replace('{original}', JSON.stringify(original))
      .replace('{proposed}', JSON.stringify(proposed))
      .replace('{plan}', JSON.stringify(plan));

    const response = await this.ask(prompt, ARC_PROMPTS.review.system);
    return this.extractJSON(response) || { score: 0, passed: false, issues: [] };
  }

  async process(request, context = {}) {
    const startTime = Date.now();
    this.history = [];

    try {
      const gathered = await this.scanner.scan(request, context);

      const analysis = await this.analyze(request, {
        files: gathered.files,
        edits: context.edits || []
      });
      this.history.push({ stage: 'analysis', data: analysis });

      const plan = await this.plan(request, analysis, gathered.snippets);
      this.history.push({ stage: 'plan', data: plan });

      let code = await this.generateCode(plan, gathered.existingCode);
      this.history.push({ stage: 'code', data: code });

      let reviewResult;
      let loops = 0;

      do {
        reviewResult = await this.review(gathered.existingCode, code, plan);
        this.history.push({ stage: 'review', data: reviewResult });

        if (!reviewResult.passed && reviewResult.score < this.config.qualityThreshold && loops < this.config.maxReviewLoops) {
          const refinePrompt = ARC_PROMPTS.refine.user
            .replace('{code}', JSON.stringify(code))
            .replace('{issues}', JSON.stringify(reviewResult.issues))
            .replace('{plan}', JSON.stringify(plan));

          const refined = await this.ask(refinePrompt, ARC_PROMPTS.refine.system);
          code = this.extractJSON(refined) || code;
          loops++;
        } else {
          break;
        }
      } while (loops < this.config.maxReviewLoops);

      const elapsed = Date.now() - startTime;
      this.stats.requests++;
      this.stats.avgLoops = ((this.stats.avgLoops * (this.stats.requests - 1)) + loops) / this.stats.requests;
      this.stats.avgTime = ((this.stats.avgTime * (this.stats.requests - 1)) + elapsed) / this.stats.requests;

      return {
        success: true,
        analysis,
        plan,
        code,
        review: reviewResult,
        loops,
        elapsed,
        history: this.history
      };
    } catch (err) {
      return {
        success: false,
        error: err.message,
        history: this.history
      };
    }
  }

  async buildFromIdea(idea) {
    const refinement = await this.ask(
      `Someone has this idea: "${idea}". Ask 3 clarifying questions to help them turn this into a specific software project. Keep questions simple.`,
      'You are a helpful assistant. Ask simple, clear questions. One question per line.'
    );

    return {
      originalIdea: idea,
      clarifyingQuestions: refinement.split('\n').filter(q => q.trim().length > 0),
      message: 'Answer these questions and I will build your project step by step.'
    };
  }

  async buildFromAnswers(idea, answers) {
    const fullRequest = `Build a complete project based on this idea and answers:\n\nIDEA: ${idea}\n\nANSWERS:\n${answers}\n\nCreate a full working application.`;
    return this.process(fullRequest);
  }

  getStats() {
    return { ...this.stats };
  }
}

module.exports = { ARCAgent };
