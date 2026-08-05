// test-agent.js - ARC Agent quality benchmark
const { ARCAgent } = require('./arc-agent');

const BENCHMARK_TESTS = [
  {
    name: 'Simple function',
    request: 'Write a function that takes an array of numbers and returns the sum of all even numbers',
    expectedOutcome: 'function sumEven',
    checkOutput: (code) => {
      try {
        eval(code);
        return sumEven([1,2,3,4,5,6]) === 12;
      } catch { return false; }
    }
  },
  {
    name: 'Error handling',
    request: 'Add try-catch error handling to this function:\nfunction fetchData(url) { return fetch(url).then(r => r.json()) }',
    expectedOutcome: 'try',
    checkOutput: (code) => code.includes('try') && code.includes('catch')
  },
  {
    name: 'Bug fix',
    request: 'Fix the off-by-one error: for(let i=0; i<=array.length; i++) { console.log(array[i]) }',
    expectedOutcome: '< array.length',
    checkOutput: (code) => code.includes('< array.length') || code.includes('< arr.length')
  },
  {
    name: 'Refactoring',
    request: 'Convert this callback to async/await:\nfunction getData(callback) { fs.readFile("data.json", (err, data) => { callback(JSON.parse(data)) }) }',
    expectedOutcome: 'async',
    checkOutput: (code) => code.includes('async') && code.includes('await')
  },
  {
    name: 'Security check',
    request: 'Add SQL injection prevention to: const query = "SELECT * FROM users WHERE id = " + userId',
    expectedOutcome: 'parameterized',
    checkOutput: (code) => code.includes('?') || code.includes('$1') || code.toLowerCase().includes('parameter')
  }
];

async function runBenchmarks() {
  console.log('🧪 Running ARC Agent Benchmarks\n');
  console.log('═'.repeat(60));
  
  const agent = new ARCAgent();
  await agent.initialize();
  
  let passed = 0;
  const results = [];
  
  for (const test of BENCHMARK_TESTS) {
    console.log(`\n📋 Test: ${test.name}`);
    console.log(`Request: "${test.request.substring(0, 80)}..."`);
    
    const startTime = Date.now();
    
    try {
      const result = await agent.processRequest(test.request, {
        openFiles: [],
        recentEdits: []
      });
      
      const latency = Date.now() - startTime;
      
      // Extract generated code for checking
      let generatedCode = '';
      if (result.code?.patches?.[0]?.diff) {
        const addedLines = result.code.patches[0].diff
          .split('\n')
          .filter(l => l.startsWith('+'))
          .map(l => l.substring(1))
          .join('\n');
        generatedCode = addedLines;
      }
      
      const testPassed = test.checkOutput(generatedCode);
      
      results.push({
        name: test.name,
        passed: testPassed,
        latency,
        reviewScore: result.review?.score || 0,
        reviewLoops: result.refinements
      });
      
      if (testPassed) passed++;
      
      console.log(`${testPassed ? '✅' : '❌'} ${test.name} (${latency}ms, score: ${result.review?.score?.toFixed(2) || 'N/A'})`);
      if (!testPassed) {
        console.log(`   Expected: ${test.expectedOutcome}`);
        console.log(`   Got: ${generatedCode.substring(0, 100)}`);
      }
      
    } catch (err) {
      console.log(`❌ ${test.name} - Error: ${err.message}`);
      results.push({ name: test.name, passed: false, error: err.message });
    }
  }
  
  // Summary
  console.log('\n' + '═'.repeat(60));
  console.log('📊 BENCHMARK RESULTS');
  console.log('═'.repeat(60));
  console.log(`Passed: ${passed}/${BENCHMARK_TESTS.length} (${((passed/BENCHMARK_TESTS.length)*100).toFixed(1)}%)`);
  console.log(`Avg Latency: ${Math.round(results.reduce((sum, r) => sum + (r.latency || 0), 0) / results.length)}ms`);
  console.log(`Avg Review Score: ${(results.reduce((sum, r) => sum + (r.reviewScore || 0), 0) / results.length).toFixed(2)}`);
  
  const telemetry = agent.getTelemetry();
  console.log(`\nAgent Telemetry:`, telemetry);
  
  await agent.shutdown();
  
  return { passed, total: BENCHMARK_TESTS.length, results };
}

// Run if called directly
if (require.main === module) {
  runBenchmarks().then(({ passed, total }) => {
    process.exit(passed === total ? 0 : 1);
  });
}

module.exports = { runBenchmarks, BENCHMARK_TESTS };
