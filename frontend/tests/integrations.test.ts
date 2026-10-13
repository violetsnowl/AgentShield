import { describe, it, expect } from 'vitest';
import { adaptResult, boundaryVersion, evidenceStatePresentation } from '../src/integrations';
describe('versioned D boundary, no invented A/C wire contracts', () => {
  it.each(['LossResult', 'QuoteResult'] as const)('%s remains pending without owner data', kind => {
    for (const input of [null, undefined]) {
      expect(adaptResult(kind, input)).toMatchObject({ state: 'pending', result: null, commercial_quote: false, boundary_version: boundaryVersion });
    }
  });
  it.each(['LossResult', 'QuoteResult'] as const)('%s refuses an unreviewed version or arbitrary result', kind => {
    for (const input of [{}, { version: 'invented', amount_cents: 0 }, { commercial_quote: true }, 'unknown']) {
      expect(adaptResult(kind, input)).toMatchObject({ state: 'unsupported_contract', result: null, commercial_quote: false });
    }
  });
  it('keeps all required V1.1 unavailable states readable without numeric results', () => {
    expect(Object.keys(evidenceStatePresentation)).toEqual(['not_fitted', 'insufficient_evidence', 'partial', 'out_of_scope']);
    expect(evidenceStatePresentation.insufficient_evidence.text).toContain('null');
    expect(evidenceStatePresentation.out_of_scope.tone).toBe('error');
  });
});
