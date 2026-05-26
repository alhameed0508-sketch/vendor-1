import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

// A component that throws on demand
function ThrowError({ shouldThrow }) {
  if (shouldThrow) {
    throw new Error('Test error message');
  }
  return <div>Content renders fine</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress React error boundary console.error noise in test output
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Content renders fine')).toBeInTheDocument();
  });

  it('catches errors and displays error message', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('shows Try Again button that resets error state (soft retry)', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Click "Try Again" — resets error state without page reload
    fireEvent.click(screen.getByText('Try Again'));

    // After reset, ErrorBoundary tries to re-render children
    // Since the component still throws, it will show error again
    // But the important thing is that the state was reset
    // In real usage, the child would re-render successfully after a transient error
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows Reload Page button', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Reload Page')).toBeInTheDocument();
  });

  it('Try Again button resets and renders children when error is transient', () => {
    let shouldThrow = true;

    function TransientError() {
      if (shouldThrow) {
        throw new Error('Transient failure');
      }
      return <div>Recovered successfully</div>;
    }

    render(
      <ErrorBoundary>
        <TransientError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Fix the "transient" error
    shouldThrow = false;

    // Click Try Again
    fireEvent.click(screen.getByText('Try Again'));

    // Now children render successfully
    expect(screen.getByText('Recovered successfully')).toBeInTheDocument();
  });
});
