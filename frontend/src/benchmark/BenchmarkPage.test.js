import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BenchmarkPage, { summarizeBenchmark } from './BenchmarkPage';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({
  apiFetch: jest.fn(),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const response = data => ({
  ok: true,
  status: 200,
  json: async () => ({ success: true, data }),
});

describe('BenchmarkPage', () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  test('connects all five controls to executable benchmark APIs', async () => {
    apiFetch
      .mockResolvedValueOnce(
        response({
          execution_enabled: true,
          available_benchmarks: [
            'synthetic',
            'adversarial',
            'cross_validation',
            'comparison',
            'full_evaluation',
          ],
        })
      )
      .mockResolvedValueOnce(response({ results: [] }))
      .mockResolvedValueOnce(
        response({
          dataset_name: 'synthetic_3clusters',
          precision: 0.8,
          recall: 0.75,
          f1_score: 0.7742,
          accuracy: 0.9,
          total_accounts: 60,
          total_transactions: 300,
          alerts_generated: 4,
          elapsed_seconds: 0.25,
        })
      )
      .mockResolvedValueOnce(response({ results: [{ run_id: 'BENCH_1' }] }));

    render(<BenchmarkPage />);

    for (const label of [
      'Synthetic',
      'Adversarial',
      'Cross-Validation',
      'Comparison',
      'Full Evaluation',
    ]) {
      expect(
        await screen.findByRole('button', {
          name: new RegExp(`Run ${label} benchmark`, 'i'),
        })
      ).toBeEnabled();
    }

    await userEvent.click(
      screen.getByRole('button', { name: /Run Synthetic benchmark/i })
    );

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/benchmark/synthetic',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ num_clusters: 3, num_legit_accounts: 30 }),
        })
      );
    });
    expect(await screen.findByText('80.0%')).toBeInTheDocument();
    expect(screen.getByText('90.0%')).toBeInTheDocument();
  });

  test('disables synthetic execution when backend reports production mode', async () => {
    apiFetch
      .mockResolvedValueOnce(
        response({
          execution_enabled: false,
          restriction: 'Synthetic execution is disabled in production.',
        })
      )
      .mockResolvedValueOnce(response({ results: [] }));

    render(<BenchmarkPage />);

    expect(
      await screen.findByText('Synthetic execution is disabled in production.')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Run Full Evaluation benchmark/i })
    ).toBeDisabled();
  });

  test('labels the page in sentence case without middle dots', async () => {
    apiFetch
      .mockResolvedValueOnce(response({ execution_enabled: true }))
      .mockResolvedValueOnce(response({ results: [] }));

    render(<BenchmarkPage />);

    const heading = await screen.findByRole('heading', { name: 'Model Benchmarks' });
    expect(screen.getByText('Evaluation')).toBeInTheDocument();
    expect(heading.parentElement.nextSibling.textContent).not.toMatch('·');
  });
});

test('summarizes cross-validation metrics for the top cards', () => {
  expect(
    summarizeBenchmark({
      num_folds: 5,
      mean_precision: 0.8,
      mean_recall: 0.7,
      mean_f1: 0.7467,
      mean_accuracy: 0.9,
      fold_results: [{ test_accounts: 10 }, { test_accounts: 10 }],
    })
  ).toEqual(
    expect.objectContaining({
      precision: 0.8,
      recall: 0.7,
      f1_score: 0.7467,
      accuracy: 0.9,
      total_accounts: 20,
    })
  );
});

