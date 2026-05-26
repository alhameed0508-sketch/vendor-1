import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from './Sidebar';
import { ThemeProvider } from '../ThemeContext';

// Mock lucide-react icons to avoid rendering issues in tests
jest.mock('lucide-react', () => ({
  AlertTriangle: () => <div data-testid="icon-alert-triangle" />,
  BarChart2: () => <div data-testid="icon-bar-chart" />,
  Shield: () => <div data-testid="icon-shield" />,
  ChevronLeft: () => <div data-testid="icon-chevron-left" />,
  ChevronRight: () => <div data-testid="icon-chevron-right" />,
  Activity: () => <div data-testid="icon-activity" />,
  Moon: () => <div data-testid="icon-moon" />,
  Sun: () => <div data-testid="icon-sun" />,
  Zap: () => <div data-testid="icon-zap" />,
  FileCheck: () => <div data-testid="icon-file-check" />,
  UserCheck: () => <div data-testid="icon-user-check" />,
  Presentation: () => <div data-testid="icon-presentation" />,
}));

// Helper to render Sidebar with all required providers
const renderSidebar = (props = {}, initialRoute = '/') => {
  const defaultProps = {
    stats: null,
    collapsed: false,
    onToggle: jest.fn(),
    ...props,
  };

  return {
    ...render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <ThemeProvider>
          <Sidebar {...defaultProps} />
        </ThemeProvider>
      </MemoryRouter>
    ),
    props: defaultProps,
  };
};

describe('Sidebar Component', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('Navigation Items', () => {
    test('renders all 5 NAV_ITEMS', () => {
      renderSidebar();

      expect(screen.getByText('Alert Queue')).toBeInTheDocument();
      expect(screen.getByText('ROI Analytics')).toBeInTheDocument();
      expect(screen.getByText('Compliance')).toBeInTheDocument();
      expect(screen.getByText('Onboarding')).toBeInTheDocument();
      expect(screen.getByText('Judge View')).toBeInTheDocument();
    });

    test('renders navigation items with correct links', () => {
      renderSidebar();

      const alertQueueLink = screen.getByText('Alert Queue').closest('a');
      const analyticsLink = screen.getByText('ROI Analytics').closest('a');
      const complianceLink = screen.getByText('Compliance').closest('a');
      const onboardingLink = screen.getByText('Onboarding').closest('a');
      const judgeLink = screen.getByText('Judge View').closest('a');

      expect(alertQueueLink).toHaveAttribute('href', '/');
      expect(analyticsLink).toHaveAttribute('href', '/analytics');
      expect(complianceLink).toHaveAttribute('href', '/compliance');
      expect(onboardingLink).toHaveAttribute('href', '/onboarding');
      expect(judgeLink).toHaveAttribute('href', '/judge');
    });

    test('renders navigation items with icons', () => {
      renderSidebar();

      expect(screen.getByTestId('icon-alert-triangle')).toBeInTheDocument();
      expect(screen.getByTestId('icon-bar-chart')).toBeInTheDocument();
      expect(screen.getByTestId('icon-file-check')).toBeInTheDocument();
      expect(screen.getByTestId('icon-user-check')).toBeInTheDocument();
      expect(screen.getByTestId('icon-presentation')).toBeInTheDocument();
    });
  });

  describe('Active State Highlighting', () => {
    test('highlights Alert Queue as active when on root path', () => {
      renderSidebar({}, '/');

      const alertQueueLink = screen.getByText('Alert Queue').closest('a');
      expect(alertQueueLink).toHaveClass('sidebar-link-active');
    });

    test('highlights ROI Analytics as active when on /analytics path', () => {
      renderSidebar({}, '/analytics');

      const analyticsLink = screen.getByText('ROI Analytics').closest('a');
      expect(analyticsLink).toHaveClass('sidebar-link-active');
    });

    test('highlights Compliance as active when on /compliance path', () => {
      renderSidebar({}, '/compliance');

      const complianceLink = screen.getByText('Compliance').closest('a');
      expect(complianceLink).toHaveClass('sidebar-link-active');
    });

    test('highlights Onboarding as active when on /onboarding path', () => {
      renderSidebar({}, '/onboarding');

      const onboardingLink = screen.getByText('Onboarding').closest('a');
      expect(onboardingLink).toHaveClass('sidebar-link-active');
    });

    test('highlights Judge View as active when on /judge path', () => {
      renderSidebar({}, '/judge');

      const judgeLink = screen.getByText('Judge View').closest('a');
      expect(judgeLink).toHaveClass('sidebar-link-active');
    });

    test('does not highlight Alert Queue when on other paths', () => {
      renderSidebar({}, '/analytics');

      const alertQueueLink = screen.getByText('Alert Queue').closest('a');
      expect(alertQueueLink).not.toHaveClass('sidebar-link-active');
    });

    test('shows active bar indicator for active route', () => {
      renderSidebar({}, '/analytics');

      // The active bar is rendered within the active link
      const analyticsLink = screen.getByText('ROI Analytics').closest('a');
      const activeBar = analyticsLink.querySelector('.sidebar-active-bar');
      expect(activeBar).toBeInTheDocument();
    });
  });

  describe('Navigation Behavior', () => {
    test('clicking a nav item navigates to the correct path', async () => {
      const user = userEvent.setup();
      renderSidebar({}, '/');

      const analyticsLink = screen.getByText('ROI Analytics');
      await user.click(analyticsLink);

      // After navigation, the link should be active
      await waitFor(() => {
        expect(analyticsLink.closest('a')).toHaveClass('sidebar-link-active');
      });
    });

    test('navigation works for all routes', async () => {
      const user = userEvent.setup();
      renderSidebar({}, '/');

      // Test each navigation item
      const routes = [
        { text: 'ROI Analytics', expectedActive: 'sidebar-link-active' },
        { text: 'Compliance', expectedActive: 'sidebar-link-active' },
        { text: 'Onboarding', expectedActive: 'sidebar-link-active' },
        { text: 'Judge View', expectedActive: 'sidebar-link-active' },
      ];

      for (const route of routes) {
        const link = screen.getByText(route.text);
        await user.click(link);

        await waitFor(() => {
          expect(link.closest('a')).toHaveClass(route.expectedActive);
        });
      }
    });
  });

  describe('Theme Toggle', () => {
    test('renders theme toggle button', () => {
      renderSidebar();

      const themeButton = screen.getByRole('button', { name: /toggle theme/i });
      expect(themeButton).toBeInTheDocument();
    });

    test('shows Moon icon and "Dark Mode" text in light theme', async () => {
      renderSidebar();

      // Theme starts as dark, so toggle to light
      const themeButton = screen.getByRole('button', { name: /toggle theme/i });
      const user = userEvent.setup();
      await user.click(themeButton);

      await waitFor(() => {
        expect(screen.getByTestId('icon-moon')).toBeInTheDocument();
        expect(screen.getByText('Dark Mode')).toBeInTheDocument();
      });
    });

    test('shows Sun icon and "Light Mode" text in dark theme', () => {
      renderSidebar();

      expect(screen.getByTestId('icon-sun')).toBeInTheDocument();
      expect(screen.getByText('Light Mode')).toBeInTheDocument();
    });

    test('toggles theme when clicked', async () => {
      renderSidebar();

      const themeButton = screen.getByRole('button', { name: /toggle theme/i });
      const user = userEvent.setup();

      // Initial state: dark theme (Sun icon, "Light Mode" text)
      expect(screen.getByTestId('icon-sun')).toBeInTheDocument();
      expect(screen.getByText('Light Mode')).toBeInTheDocument();

      // Click to toggle to light theme
      await user.click(themeButton);

      await waitFor(() => {
        expect(screen.getByTestId('icon-moon')).toBeInTheDocument();
        expect(screen.getByText('Dark Mode')).toBeInTheDocument();
      });

      // Click again to toggle back to dark theme
      await user.click(themeButton);

      await waitFor(() => {
        expect(screen.getByTestId('icon-sun')).toBeInTheDocument();
        expect(screen.getByText('Light Mode')).toBeInTheDocument();
      });
    });
  });

  describe('Collapse Toggle', () => {
    test('renders collapse button', () => {
      renderSidebar();

      const collapseButton = screen.getByRole('button', { name: /collapse sidebar/i });
      expect(collapseButton).toBeInTheDocument();
    });

    test('calls onToggle when collapse button is clicked', async () => {
      const onToggle = jest.fn();
      renderSidebar({ onToggle });

      const collapseButton = screen.getByRole('button', { name: /collapse sidebar/i });
      const user = userEvent.setup();
      await user.click(collapseButton);

      expect(onToggle).toHaveBeenCalledTimes(1);
    });

    test('shows ChevronLeft icon when expanded', () => {
      renderSidebar({ collapsed: false });

      expect(screen.getByTestId('icon-chevron-left')).toBeInTheDocument();
    });

    test('shows ChevronRight icon when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.getByTestId('icon-chevron-right')).toBeInTheDocument();
    });

    test('has correct aria-label when expanded', () => {
      renderSidebar({ collapsed: false });

      const collapseButton = screen.getByRole('button', { name: /collapse sidebar/i });
      expect(collapseButton).toHaveAttribute('aria-label', 'Collapse sidebar');
    });

    test('has correct aria-label when collapsed', () => {
      renderSidebar({ collapsed: true });

      const collapseButton = screen.getByRole('button', { name: /expand sidebar/i });
      expect(collapseButton).toHaveAttribute('aria-label', 'Expand sidebar');
    });
  });

  describe('Collapsed State', () => {
    test('hides nav item labels when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.queryByText('Alert Queue')).not.toBeInTheDocument();
      expect(screen.queryByText('ROI Analytics')).not.toBeInTheDocument();
      expect(screen.queryByText('Compliance')).not.toBeInTheDocument();
      expect(screen.queryByText('Onboarding')).not.toBeInTheDocument();
      expect(screen.queryByText('Judge View')).not.toBeInTheDocument();
    });

    test('shows nav item labels when expanded', () => {
      renderSidebar({ collapsed: false });

      expect(screen.getByText('Alert Queue')).toBeInTheDocument();
      expect(screen.getByText('ROI Analytics')).toBeInTheDocument();
      expect(screen.getByText('Compliance')).toBeInTheDocument();
      expect(screen.getByText('Onboarding')).toBeInTheDocument();
      expect(screen.getByText('Judge View')).toBeInTheDocument();
    });

    test('hides logo text when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.queryByText('MuleCatch')).not.toBeInTheDocument();
    });

    test('shows logo text when expanded', () => {
      renderSidebar({ collapsed: false });

      expect(screen.getByText('MuleCatch')).toBeInTheDocument();
    });

    test('hides system tagline when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.queryByText('// IOB Fraud Intelligence')).not.toBeInTheDocument();
    });

    test('shows system tagline when expanded', () => {
      renderSidebar({ collapsed: false });

      expect(screen.getByText('// IOB Fraud Intelligence')).toBeInTheDocument();
    });

    test('adds sidebar-collapsed class when collapsed', () => {
      const { container } = renderSidebar({ collapsed: true });

      const sidebar = container.querySelector('.sidebar');
      expect(sidebar).toHaveClass('sidebar-collapsed');
    });

    test('does not add sidebar-collapsed class when expanded', () => {
      const { container } = renderSidebar({ collapsed: false });

      const sidebar = container.querySelector('.sidebar');
      expect(sidebar).not.toHaveClass('sidebar-collapsed');
    });

    test('shows title attribute on nav items when collapsed', () => {
      renderSidebar({ collapsed: true });

      const links = screen.getAllByRole('link');
      const alertQueueLink = links.find(link => link.getAttribute('title') === 'Alert Queue');
      const analyticsLink = links.find(link => link.getAttribute('title') === 'ROI Analytics');

      expect(alertQueueLink).toBeInTheDocument();
      expect(analyticsLink).toBeInTheDocument();
    });
  });

  describe('Alert Stats Display', () => {
    test('does not show stats when stats prop is null', () => {
      renderSidebar({ stats: null });

      expect(screen.queryByText('Live Queue')).not.toBeInTheDocument();
    });

    test('does not show stats when stats prop is undefined', () => {
      renderSidebar({ stats: undefined });

      expect(screen.queryByText('Live Queue')).not.toBeInTheDocument();
    });

    test('shows stats when provided and not collapsed', () => {
      const stats = { critical: 5, high: 10, medium: 15 };
      renderSidebar({ stats, collapsed: false });

      expect(screen.getByText('Live Queue')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    test('does not show stats when collapsed even if stats are provided', () => {
      const stats = { critical: 5, high: 10, medium: 15 };
      renderSidebar({ stats, collapsed: true });

      expect(screen.queryByText('Live Queue')).not.toBeInTheDocument();
    });

    test('does not show stats when total alerts is 0', () => {
      const stats = { critical: 0, high: 0, medium: 0 };
      renderSidebar({ stats, collapsed: false });

      expect(screen.queryByText('Live Queue')).not.toBeInTheDocument();
    });

    test('shows stats when at least one severity has alerts', () => {
      const stats = { critical: 0, high: 1, medium: 0 };
      renderSidebar({ stats, collapsed: false });

      expect(screen.getByText('Live Queue')).toBeInTheDocument();
    });

    test('handles missing severity counts gracefully', () => {
      const stats = { critical: 5 }; // high and medium are undefined
      renderSidebar({ stats, collapsed: false });

      expect(screen.getByText('Live Queue')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('System Health Indicator', () => {
    test('shows system online indicator when expanded', () => {
      renderSidebar({ collapsed: false });

      expect(screen.getByText('System Online')).toBeInTheDocument();
    });

    test('hides system online indicator when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.queryByText('System Online')).not.toBeInTheDocument();
    });
  });

  describe('Logo and Branding', () => {
    test('always shows logo monogram', () => {
      renderSidebar();

      expect(screen.getByText('MC')).toBeInTheDocument();
    });

    test('shows logo monogram even when collapsed', () => {
      renderSidebar({ collapsed: true });

      expect(screen.getByText('MC')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('all nav links are accessible', () => {
      renderSidebar();

      const links = screen.getAllByRole('link');
      expect(links.length).toBeGreaterThanOrEqual(5); // At least 5 nav items
    });

    test('all interactive buttons have aria-labels', () => {
      renderSidebar();

      const themeButton = screen.getByRole('button', { name: /toggle theme/i });
      const collapseButton = screen.getByRole('button', { name: /collapse sidebar/i });

      expect(themeButton).toHaveAttribute('aria-label');
      expect(collapseButton).toHaveAttribute('aria-label');
    });

    test('nav links have title attribute when collapsed for accessibility', () => {
      renderSidebar({ collapsed: true });

      const links = screen.getAllByRole('link');
      links.forEach(link => {
        const title = link.getAttribute('title');
        // Only nav items should have title when collapsed
        if (title) {
          expect(['Alert Queue', 'ROI Analytics', 'Compliance', 'Onboarding', 'Judge View']).toContain(title);
        }
      });
    });
  });
});
