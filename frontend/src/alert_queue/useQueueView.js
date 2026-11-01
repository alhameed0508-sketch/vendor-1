import { useState, useCallback } from 'react';

const KEY = 'mulecatch-queue-view';
const VIEWS = ['board', 'table'];

function readView() {
  try {
    const v = window.localStorage.getItem(KEY);
    return VIEWS.includes(v) ? v : 'table';
  } catch {
    return 'table';
  }
}

export default function useQueueView() {
  const [view, setViewState] = useState(readView);
  const setView = useCallback(v => {
    setViewState(v);
    try {
      window.localStorage.setItem(KEY, v);
    } catch {
      // storage unavailable: view still works for this session
    }
  }, []);
  return [view, setView];
}
