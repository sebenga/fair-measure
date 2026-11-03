import { environment } from '../../environments/environment';

/**
 * True for requests to our API. Paginated `next` links come back absolute
 * (`https://host/api/v1/...`) even when the app is built with a relative base.
 */
export function isApiUrl(url: string): boolean {
  const base = environment.apiBaseUrl;
  if (url.startsWith(base)) return true;
  if (!base.startsWith('/') || typeof location === 'undefined') return false;
  try {
    const target = new URL(url, location.origin);
    return target.origin === location.origin && target.pathname.startsWith(base);
  } catch {
    return false;
  }
}
