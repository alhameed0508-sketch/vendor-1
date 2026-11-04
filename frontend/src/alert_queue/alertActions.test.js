import { apiFetch } from '../auth/api';
import { updateAlertStatus, fileStr } from './alertActions';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const ok = { ok: true, status: 200 };
const bad = { ok: false, status: 500 };
const alert = { alert_id: 'ALT-1', status: 'UNDER_REVIEW' };

beforeEach(() => apiFetch.mockReset());

describe('updateAlertStatus', () => {
  it('PATCHes the status', async () => {
    apiFetch.mockResolvedValue(ok);
    await updateAlertStatus('ALT-1', 'RESOLVED');
    const [url, init] = apiFetch.mock.calls[0];
    expect(url).toBe('/api/v1/alerts/ALT-1');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body)).toEqual({ status: 'RESOLVED' });
  });

  it('throws when the response is not ok', async () => {
    apiFetch.mockResolvedValue(bad);
    await expect(updateAlertStatus('ALT-1', 'RESOLVED')).rejects.toThrow();
  });
});

describe('fileStr', () => {
  it('exports the STR first, then sets STR_FILED with the reason as notes', async () => {
    apiFetch.mockResolvedValue(ok);
    await fileStr(alert, 'layering');
    expect(apiFetch.mock.calls[0][0]).toBe('/api/v1/compliance/str-export');
    expect(JSON.parse(apiFetch.mock.calls[0][1].body)).toEqual({ alert_ids: ['ALT-1'] });
    expect(apiFetch.mock.calls[1][0]).toBe('/api/v1/alerts/ALT-1');
    expect(JSON.parse(apiFetch.mock.calls[1][1].body)).toEqual({
      status: 'STR_FILED', investigator_notes: 'layering',
    });
  });

  it('does not PATCH when the export fails', async () => {
    apiFetch.mockResolvedValue(bad);
    await expect(fileStr(alert, 'x')).rejects.toThrow();
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it('throws when the PATCH fails after a successful export', async () => {
    apiFetch.mockResolvedValueOnce(ok).mockResolvedValueOnce(bad);
    await expect(fileStr(alert, 'x')).rejects.toThrow();
  });
});
