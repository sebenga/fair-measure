const RELOADED_AT = 'fm.staleBuildReload';
/** Don't reload again if the last attempt was this recent: the file really is missing. */
const RETRY_AFTER_MS = 30_000;

/** Chrome, Safari (iPhone) and Firefox wording for a lazy-loaded file that no longer exists. */
const STALE_CHUNK =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|ChunkLoadError|Loading chunk [\w-]+ failed/i;

export function isStaleBuildError(error: unknown): boolean {
  const inner = (error as { rejection?: unknown } | null)?.rejection ?? error;
  const message = inner instanceof Error ? inner.message : String(inner ?? '');
  return STALE_CHUNK.test(message);
}

/**
 * A tab opened before a deploy still runs the old app, whose code files the
 * new deploy removed. Load the page again (once) so it picks up the new app.
 * Returns false when it already tried recently and the caller should show the error.
 */
export function reloadForNewBuild(url?: string): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOADED_AT) || 0);
    if (Date.now() - last < RETRY_AFTER_MS) return false;
    sessionStorage.setItem(RELOADED_AT, String(Date.now()));
  } catch {
    // Private mode without storage: still worth one reload.
  }
  if (url) location.assign(url);
  else location.reload();
  return true;
}
