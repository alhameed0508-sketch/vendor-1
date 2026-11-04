import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ApprovalDialog from './ApprovalDialog';

const alert = { alert_id: 'ALT-1', status: 'UNDER_REVIEW' };

describe('ApprovalDialog', () => {
  it('disables confirm until a reason is typed', async () => {
    render(<ApprovalDialog alert={alert} onConfirm={jest.fn()} onCancel={jest.fn()} />);
    const confirm = screen.getByRole('button', { name: /confirm filing/i });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/reason for filing/i), 'layering pattern');
    expect(confirm).toBeEnabled();
  });

  it('calls onConfirm once with the reason', async () => {
    const onConfirm = jest.fn().mockResolvedValue();
    render(<ApprovalDialog alert={alert} onConfirm={onConfirm} onCancel={jest.fn()} />);
    await userEvent.type(screen.getByLabelText(/reason for filing/i), 'layering pattern');
    await userEvent.click(screen.getByRole('button', { name: /confirm filing/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm).toHaveBeenCalledWith('layering pattern');
  });

  it('Escape cancels and never confirms', async () => {
    const onConfirm = jest.fn();
    const onCancel = jest.fn();
    render(<ApprovalDialog alert={alert} onConfirm={onConfirm} onCancel={onCancel} />);
    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('shows the error and stays open when onConfirm rejects', async () => {
    const onConfirm = jest.fn().mockRejectedValue(new Error('PATCH failed'));
    render(<ApprovalDialog alert={alert} onConfirm={onConfirm} onCancel={jest.fn()} />);
    await userEvent.type(screen.getByLabelText(/reason for filing/i), 'x');
    await userEvent.click(screen.getByRole('button', { name: /confirm filing/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('PATCH failed');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
