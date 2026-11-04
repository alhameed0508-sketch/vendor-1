import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import CapturePage from './CapturePage';
import { apiFetch } from '../auth/api';
import { claimView, ok } from './fixtures';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const fill = async () => {
  await userEvent.type(screen.getByLabelText('Customer ID'), 'C1');
  await userEvent.type(screen.getByLabelText('Customer name'), 'Test Buyer');
  await userEvent.type(screen.getByLabelText('Item'), 'Kettle');
  await userEvent.type(screen.getByLabelText('Amount (₹)'), '2500');
  await userEvent.type(screen.getByLabelText('Reason given'), 'Lid is broken');
  await userEvent.type(screen.getByLabelText('Delivered'), '2027-02-10T12:00');
  await userEvent.type(screen.getByLabelText('Return requested'), '2027-02-12T12:00');
};

describe('CapturePage', () => {
  beforeEach(() => apiFetch.mockReset());

  it('asks the phone camera for the photo and the receipt', () => {
    render(<MemoryRouter><CapturePage /></MemoryRouter>);
    expect(screen.getByLabelText('Photo of the item')).toHaveAttribute('capture', 'environment');
    expect(screen.getByLabelText('Receipt')).toHaveAttribute('capture', 'environment');
  });

  it('files the claim with the photo as base64 and shows the recommendation', async () => {
    apiFetch.mockResolvedValue(ok({ ...claimView('RC-2001'), fusion: { tier: 'APPROVE', score: 1 } }));
    render(<MemoryRouter><CapturePage /></MemoryRouter>);
    await fill();
    await userEvent.upload(screen.getByLabelText('Photo of the item'), new File(['abc'], 'p.jpg', { type: 'image/jpeg' }));
    await userEvent.click(screen.getByRole('button', { name: 'Check this return' }));
    expect(await screen.findByText('Recommendation')).toBeInTheDocument();
    const body = JSON.parse(apiFetch.mock.calls[0][1].body);
    expect(body.photo_b64).toBe('YWJj');
    expect(body.amount).toBe(2500);
    expect(body.receipt_pdf_b64).toBeUndefined();
    expect(screen.getByRole('link', { name: 'Open the case' })).toHaveAttribute('href', '/returns/RC-2001');
  });

  it('shows the reason a claim is refused', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 400, json: () => Promise.resolve({ success: false, error: { message: 'A return cannot happen before delivery' } }) });
    render(<MemoryRouter><CapturePage /></MemoryRouter>);
    await fill();
    await userEvent.click(screen.getByRole('button', { name: 'Check this return' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('A return cannot happen before delivery');
  });
});
