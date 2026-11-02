import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import MobileNav from './MobileNav';
import { ThemeProvider } from '../ThemeContext';

jest.mock('lucide-react', () => ({
  AlertTriangle: () => <span />,
  BarChart2: () => <span />,
  FileCheck: () => <span />,
  Gauge: () => <span />,
  MoreHorizontal: () => <span />,
  Moon: () => <span />,
  Network: () => <span />,
  Sun: () => <span />,
  Upload: () => <span />,
  UserCheck: () => <span />,
  X: () => <span />,
  Zap: () => <span />,
}));

const renderNav = (route = '/') => render(
  <MemoryRouter initialEntries={[route]}>
    <ThemeProvider>
      <MobileNav />
    </ThemeProvider>
  </MemoryRouter>
);

describe('MobileNav', () => {
  beforeEach(() => localStorage.clear());

  test('shows the three core pages and a More button in the tab bar', () => {
    renderNav();
    const tabs = screen.getByRole('navigation', { name: 'Main' });
    expect(tabs).toHaveTextContent('Alerts');
    expect(tabs).toHaveTextContent('Triage');
    expect(tabs).toHaveTextContent('Network');
    expect(screen.getByRole('button', { name: 'More pages' })).toBeInTheDocument();
  });

  test('marks the current page tab', () => {
    renderNav('/queue');
    expect(screen.getByRole('link', { name: 'Triage' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Alerts' })).not.toHaveAttribute('aria-current');
  });

  test('More opens a sheet with the other pages and a theme switch', async () => {
    renderNav();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'More pages' }));
    const sheet = screen.getByRole('dialog', { name: 'More pages' });
    ['ROI analytics', 'Compliance', 'Customer risk', 'Data import', 'Model benchmarks']
      .forEach(label => expect(sheet).toHaveTextContent(label));
    expect(screen.getByRole('button', { name: /switch to light theme/i })).toBeInTheDocument();
  });

  test('choosing a page in the sheet closes it', async () => {
    renderNav();
    await userEvent.click(screen.getByRole('button', { name: 'More pages' }));
    await userEvent.click(screen.getByRole('link', { name: 'Compliance' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('Escape and the close button both close the sheet', async () => {
    renderNav();
    await userEvent.click(screen.getByRole('button', { name: 'More pages' }));
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'More pages' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('More is highlighted when the current page lives in the sheet', () => {
    renderNav('/compliance');
    expect(screen.getByRole('button', { name: 'More pages' })).toHaveClass('mobile-tab-active');
  });
});
