// core/prompts.js - ARC stage prompts with language support

const LANGUAGES = {
  en: 'English',
  sw: 'Swahili',
  hi: 'Hindi',
  es: 'Spanish',
  fr: 'French',
  pt: 'Portuguese',
  ar: 'Arabic',
  bn: 'Bengali',
  id: 'Indonesian',
  am: 'Amharic'
};

const ARC_PROMPTS = {
  analysis: {
    system: `You are a code analyzer. Output ONLY valid JSON. No explanations.

{
  "requestType": "bug_fix|feature|refactor|explain|new_project",
  "language": "detected programming language",
  "complexity": "simple|moderate|complex",
  "files": ["relevant files"],
  "summary": "one sentence summary"
}`,

    user: `Request: {request}

Open files: {openFiles}
Recent changes: {recentEdits}

Analyze (JSON only):`
  },

  requirements: {
    system: `You are a software architect. Create a step-by-step plan. Output ONLY valid JSON.

{
  "steps": [
    {
      "step": 1,
      "action": "create|modify|delete",
      "file": "filename",
      "description": "what to do",
      "result": "expected outcome"
    }
  ],
  "dependencies": [],
  "notes": "any warnings"
}`,

    user: `Task: {task}

Analysis: {analysis}

Relevant code:
{context}

Create plan (JSON only):`
  },

  code: {
    system: `You are a programmer. Write working code. Output ONLY valid JSON.

{
  "files": [
    {
      "path": "file/path.ext",
      "content": "complete file contents",
      "description": "what this file does"
    }
  ],
  "setup": "any setup commands needed",
  "explanation": "how to use the code"
}`,

    user: `Plan: {plan}

Existing code: {existing}

Write code (JSON only):`
  },

  review: {
    system: `You are a code reviewer. Score the code from 0.0 to 1.0. Output ONLY valid JSON.

{
  "score": 0.85,
  "passed": true,
  "issues": [
    {
      "severity": "critical|major|minor",
      "file": "filename",
      "problem": "what is wrong",
      "fix": "how to fix"
    }
  ],
  "summary": "brief assessment"
}`,

    user: `Original: {original}

Proposed changes: {proposed}

Plan: {plan}

Review (JSON only):`
  },

  refine: {
    system: `You are a programmer fixing review issues. Output ONLY valid JSON in the same format as the code stage.`,

    user: `Code to fix: {code}

Issues to fix: {issues}

Original plan: {plan}

Fixed code (JSON only):`
  },

  ideaToProject: {
    system: `You help non-technical people turn ideas into software projects. Be encouraging and simple.`,

    user: `Someone who is NOT a programmer has this idea: "{idea}"

1. Explain what kind of app/program this would be (in simple terms)
2. List 3-4 questions you need answered before building it
3. Suggest a simple name for their project

Be encouraging. This person might be building something to help their community.`
  }
};

function getPrompts(language = 'en') {
  // Prompt templates are in English; user-facing output can be localized via language config
  return ARC_PROMPTS;
}

module.exports = { ARC_PROMPTS, LANGUAGES, getPrompts };
