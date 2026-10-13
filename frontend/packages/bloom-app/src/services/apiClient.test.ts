import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient, CSRF_ERROR_CODE } from './apiClient';

// axios attaches the XSRF header inside its xhr adapter, so a custom `adapter`
// would never see it. Stub XMLHttpRequest instead: the real adapter runs and
// this fake only records what was sent and plays back scripted responses.

interface Sent {
  method: string;
  url: string;
  headers: Record<string, string>;
}

interface Reply {
  status: number;
  body: unknown;
}

let sent: Sent[] = [];
let replies: Reply[] = [];

class FakeXHR {
  status = 0;
  statusText = '';
  responseText = '';
  timeout = 0;
  withCredentials = false;
  onloadend: (() => void) | null = null;
  private req: Sent = { method: '', url: '', headers: {} };

  open(method: string, url: string): void {
    this.req = { method, url, headers: {} };
  }

  setRequestHeader(name: string, value: string): void {
    this.req.headers[name.toLowerCase()] = value;
  }

  getAllResponseHeaders(): string {
    return 'content-type: application/json\r\n';
  }

  send(): void {
    sent.push(this.req);
    const reply = replies.shift() ?? { status: 200, body: {} };
    this.status = reply.status;
    this.responseText = JSON.stringify(reply.body);
    setTimeout(() => this.onloadend?.());
  }

  abort(): void {}
}

const setCookie = (value: string, name = 'kactus_xsrf_token') => {
  document.cookie = `${name}=${value}; path=/`;
};
const clearCookie = (name: string) => {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
};

const csrfFailure: Reply = { status: 403, body: { code: CSRF_ERROR_CODE } };

describe('apiClient CSRF', () => {
  beforeEach(() => {
    sent = [];
    replies = [];
    vi.stubGlobal('XMLHttpRequest', FakeXHR);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCookie('kactus_xsrf_token');
    clearCookie('XSRF-TOKEN');
  });

  it('echoes the kactus_xsrf_token cookie as X-XSRF-TOKEN', async () => {
    setCookie('abc');
    await apiClient.post('/api/portfolios', { name: 'x' });
    expect(sent[0].headers['x-xsrf-token']).toBe('abc');
  });

  it("ignores another app's generic XSRF-TOKEN cookie on the same host", async () => {
    setCookie('other-app', 'XSRF-TOKEN');
    await apiClient.post('/api/portfolios', { name: 'x' });
    expect(sent[0].headers['x-xsrf-token']).toBeUndefined();
  });

  it('refetches /me and replays once on CSRF_FAILED', async () => {
    setCookie('stale');
    replies = [csrfFailure, { status: 200, body: {} }, { status: 200, body: { ok: true } }];

    const resp = await apiClient.post('/api/portfolios', { name: 'x' });

    expect(resp.data).toEqual({ ok: true });
    expect(sent.map((r) => `${r.method} ${r.url}`)).toEqual([
      'POST /api/portfolios',
      'GET /api/auth/me',
      'POST /api/portfolios',
    ]);
  });

  it('gives up after one retry', async () => {
    replies = [csrfFailure, { status: 200, body: {} }, csrfFailure];

    await expect(apiClient.post('/api/portfolios', {})).rejects.toMatchObject({
      response: { status: 403 },
    });
    expect(sent).toHaveLength(3);
  });

  it('does not retry a 403 that is not a CSRF failure', async () => {
    replies = [{ status: 403, body: { code: 'PERMISSION_DENIED' } }];

    await expect(apiClient.post('/api/portfolios', {})).rejects.toMatchObject({
      response: { status: 403 },
    });
    expect(sent).toHaveLength(1);
  });
});
