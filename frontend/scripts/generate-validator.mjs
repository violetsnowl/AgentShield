// Compile the exact B schema at build time. CSP stays free of unsafe-eval in browsers.
import fs from 'node:fs/promises';
import Ajv from 'ajv';
import standalone from 'ajv/dist/standalone/index.js';
const schema = JSON.parse(await fs.readFile(new URL('../src/generated/evidence.schema.json', import.meta.url), 'utf8'));
const ajv = new Ajv({ strict: false, code: { source: true } });
const validator = ajv.compile(schema);
const output = '// Generated from the B EvidenceBundle schema; do not edit.\n' + standalone(ajv, validator) + '\n';
const destination = new URL('../src/generated/evidence.validator.cjs', import.meta.url);
if (process.argv.includes('--check')) {
  if (await fs.readFile(destination, 'utf8') !== output) throw new Error('Evidence validator drift');
} else await fs.writeFile(destination, output);
console.log('Browser validator matches the B schema; no runtime code generation.');
