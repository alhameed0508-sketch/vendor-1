import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RegionalStatsPanel from './RegionalStatsPanel';

const CITIES = [
  { name: 'Pune', alertCount: 9, totalVolume: 18000000, accountCount: 26, criticalCount: 7, highCount: 2, mediumCount: 0 },
  { name: 'Delhi', alertCount: 8, totalVolume: 250000, accountCount: 1, criticalCount: 0, highCount: 0, mediumCount: 8 },
];

describe('RegionalStatsPanel', () => {
  it('shows the city count and the flagged amount it is given, not a per-city sum', () => {
    render(<RegionalStatsPanel cityData={CITIES} totalVolume={12500000} />);
    expect(screen.getByText('Cities').nextSibling).toHaveTextContent('2');
    expect(screen.getByText('Flagged amount').nextSibling).toHaveTextContent('₹1.25Cr');
    expect(screen.queryByText('Total Alerts')).not.toBeInTheDocument();
  });

  it('names severity counts in words, never colour alone', () => {
    render(<RegionalStatsPanel cityData={CITIES} />);
    expect(screen.getByText('Critical 7')).toBeInTheDocument();
    expect(screen.getByText('High 2')).toBeInTheDocument();
    expect(screen.getByText('Medium 8')).toBeInTheDocument();
  });

  it('describes each city without middle dots', () => {
    render(<RegionalStatsPanel cityData={CITIES} />);
    expect(screen.getByText('26 accounts, ₹1.8Cr')).toBeInTheDocument();
    expect(screen.getByText('1 account, ₹2.5L')).toBeInTheDocument();
  });

  it('lets a keyboard user pick a city and shows which one is picked', async () => {
    const onCityClick = jest.fn();
    render(<RegionalStatsPanel cityData={CITIES} selectedCity="Pune" onCityClick={onCityClick} />);
    expect(screen.getByRole('button', { name: /Pune/ })).toHaveAttribute('aria-pressed', 'true');
    screen.getByRole('button', { name: /Delhi/ }).focus();
    await userEvent.keyboard('{Enter}');
    expect(onCityClick).toHaveBeenCalledWith('Delhi');
  });
});
