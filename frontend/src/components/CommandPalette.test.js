import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import CommandPalette from './CommandPalette';

// Mock framer-motion
jest.mock('framer-motion', () => {
  const R = require('react');
  return {
    motion: {
      div: R.forwardRef(function MotionDiv({ children, onClick, style, ...props }, ref) {
        return R.createElement('div', { ref, onClick, style }, children);
      }),
    },
    AnimatePresence: ({ children }) => children,
  };
});

// Mock cmdk — jsdom lacks the DOM measurement APIs cmdk needs
jest.mock('cmdk', () => {
  const R = require('react');

  function CommandRoot({ children, label, style }) {
    return R.createElement('div', { role: 'dialog', 'aria-label': label, style }, children);
  }

  function CommandInput({ placeholder, style }) {
    const [value, setValue] = R.useState('');
    return R.createElement('input', {
      placeholder,
      style,
      value,
      onChange: (e) => setValue(e.target.value),
    });
  }

  function CommandList({ children, style }) {
    return R.createElement('div', { style, role: 'listbox' }, children);
  }

  function CommandEmpty({ children, style }) {
    return R.createElement('div', { style }, children);
  }

  function CommandGroup({ children, heading }) {
    return R.createElement('div', { role: 'group' },
      heading ? R.createElement('div', { role: 'presentation' }, heading) : null,
      children
    );
  }

  function CommandItem({ children, value, onSelect, style }) {
    return R.createElement('div', {
      role: 'option',
      onClick: () => onSelect && onSelect(value),
      style,
      'data-value': value,
      'data-cmdk-item': '',
    }, children);
  }

  CommandRoot.Input = CommandInput;
  CommandRoot.List = CommandList;
  CommandRoot.Empty = CommandEmpty;
  CommandRoot.Group = CommandGroup;
  CommandRoot.Item = CommandItem;

  return { Command: CommandRoot };
});

const renderCommandPalette = (props = {}) => {
  const defaultProps = {
    alerts: [],
    ...props,
  };

  return render(
    <MemoryRouter>
      <CommandPalette {...defaultProps} />
    </MemoryRouter>
  );
};

describe('CommandPalette Component', () => {
  describe('Opening the Palette', () => {
    test('palette is not visible by default', () => {
      renderCommandPalette();
      expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
    });

    test('opens palette when Ctrl+K is pressed', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });
    });

    test('opens palette when Meta+K is pressed (macOS)', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Meta>}k{/Meta}');

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });
    });
  });

  describe('Closing the Palette', () => {
    test('closes palette when Escape is pressed', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');
      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
      });
    });

    test('closes palette when backdrop is clicked', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });

      // The backdrop is the first motion.div with position:fixed, inset:0
      const backdrop = document.querySelector('[style*="position: fixed"]');
      expect(backdrop).toBeInTheDocument();
      await user.click(backdrop);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
      });
    });

    test('toggles palette on repeated Ctrl+K presses', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      // Open
      await user.keyboard('{Control>}k{/Control}');
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });

      // Close
      await user.keyboard('{Control>}k{/Control}');
      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
      });
    });
  });

  describe('Page Navigation Commands', () => {
    test('displays all 5 page navigation commands', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        ['Alerts', 'Triage', 'Network', 'Risk engine', 'Live stream', 'ROI analytics', 'Compliance', 'Customer risk', 'Data import', 'Model benchmarks']
          .forEach(name => expect(screen.getByText(name)).toBeInTheDocument());
        expect(screen.queryByText('Judge View')).not.toBeInTheDocument();
        expect(screen.queryByText('Onboarding Risk')).not.toBeInTheDocument();
      });
    });

    test('page commands are grouped under "Pages" heading', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('Pages')).toBeInTheDocument();
      });
    });

    test('closes palette after selecting a page command', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');

      const analyticsItem = await screen.findByText('ROI analytics');
      await user.click(analyticsItem);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
      });
    });
  });

  describe('Alert Display', () => {
    const sampleAlerts = [
      {
        alert_id: 'ALT-001',
        severity: 'CRITICAL',
        risk_score: 0.95,
        reason_codes: ['VELOCITY_SPIKE'],
      },
      {
        alert_id: 'ALT-002',
        severity: 'HIGH',
        risk_score: 0.85,
        reason_codes: ['AMOUNT_OUTLIER'],
      },
    ];

    test('does not show Alerts group when no alerts provided', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: [] });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.queryByText('Matching alerts')).not.toBeInTheDocument();
      });
    });

    test('shows Alerts group when alerts are provided', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: sampleAlerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('Matching alerts')).toBeInTheDocument();
      });
    });

    test('displays alert IDs', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: sampleAlerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('ALT-001')).toBeInTheDocument();
        expect(screen.getByText('ALT-002')).toBeInTheDocument();
      });
    });

    test('displays alert severity badges', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: sampleAlerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('CRITICAL')).toBeInTheDocument();
        expect(screen.getByText('HIGH')).toBeInTheDocument();
      });
    });

    test('displays alert risk score as percentage', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: sampleAlerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('95%')).toBeInTheDocument();
        expect(screen.getByText('85%')).toBeInTheDocument();
      });
    });

    test('limits alerts display to 20 items', async () => {
      const manyAlerts = Array.from({ length: 25 }, (_, i) => ({
        alert_id: `ALT-${String(i + 1).padStart(3, '0')}`,
        severity: 'CRITICAL',
        risk_score: 0.95,
        reason_codes: ['VELOCITY_SPIKE'],
      }));

      const user = userEvent.setup();
      renderCommandPalette({ alerts: manyAlerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('ALT-001')).toBeInTheDocument();
        expect(screen.getByText('ALT-020')).toBeInTheDocument();
        expect(screen.queryByText('ALT-021')).not.toBeInTheDocument();
      });
    });

    test('handles alerts with missing reason_codes gracefully', async () => {
      const alerts = [
        { alert_id: 'ALT-001', severity: 'CRITICAL', risk_score: 0.95 },
      ];

      const user = userEvent.setup();
      renderCommandPalette({ alerts });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText('ALT-001')).toBeInTheDocument();
      });
    });

    test('closes palette after selecting an alert', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: sampleAlerts });

      await user.keyboard('{Control>}k{/Control}');

      const alertItem = await screen.findByText('ALT-001');
      await user.click(alertItem);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Search alerts, accounts, pages...')).not.toBeInTheDocument();
      });
    });
  });

  describe('Footer', () => {
    test('shows navigation instructions in footer', async () => {
      const user = userEvent.setup();
      renderCommandPalette();

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByText(/Navigate/i)).toBeInTheDocument();
        expect(screen.getByText(/Select/i)).toBeInTheDocument();
        expect(screen.getByText(/ESC Close/i)).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    test('handles undefined alerts prop', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: undefined });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });

      expect(screen.getByText('Alerts')).toBeInTheDocument();
    });

    test('handles null alerts prop', async () => {
      const user = userEvent.setup();
      renderCommandPalette({ alerts: null });

      await user.keyboard('{Control>}k{/Control}');

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search alerts, accounts, pages...')).toBeInTheDocument();
      });

      expect(screen.getByText('Alerts')).toBeInTheDocument();
    });
  });

  describe('Component Lifecycle', () => {
    test('cleans up event listeners on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');
      const { unmount } = renderCommandPalette();

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
      removeEventListenerSpy.mockRestore();
    });

    test('adds event listener on mount', () => {
      const addEventListenerSpy = jest.spyOn(window, 'addEventListener');
      renderCommandPalette();

      expect(addEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
      addEventListenerSpy.mockRestore();
    });
  });
});
