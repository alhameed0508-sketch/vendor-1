import { renderHook, act } from '@testing-library/react';
import useQueueView from './useQueueView';

const KEY = 'mulecatch-queue-view';

beforeEach(() => window.localStorage.clear());
afterEach(() => jest.restoreAllMocks());

it('defaults to table', () => {
  const { result } = renderHook(() => useQueueView());
  expect(result.current[0]).toBe('table');
});

it('falls back to table for an unknown stored value', () => {
  window.localStorage.setItem(KEY, 'garbage');
  const { result } = renderHook(() => useQueueView());
  expect(result.current[0]).toBe('table');
});

it('falls back to table when localStorage throws', () => {
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  const { result } = renderHook(() => useQueueView());
  expect(result.current[0]).toBe('table');
  act(() => result.current[1]('board'));
  expect(result.current[0]).toBe('board');
});

it('persists a chosen view', () => {
  const { result } = renderHook(() => useQueueView());
  act(() => result.current[1]('board'));
  expect(window.localStorage.getItem(KEY)).toBe('board');
  const again = renderHook(() => useQueueView());
  expect(again.result.current[0]).toBe('board');
});
