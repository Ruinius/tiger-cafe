import { describe, it, expect } from 'vitest';
import { normalizeLineName } from './textUtils';

describe('Text Utils', () => {
  it('normalizes line names correctly', () => {
    expect(normalizeLineName('Cash & Equivalents')).toBe('cash and equivalents');
    expect(normalizeLineName('   Total Assets   ')).toBe('total assets');
    expect(normalizeLineName('Revenue (Net)')).toBe('revenue net');
  });
});
