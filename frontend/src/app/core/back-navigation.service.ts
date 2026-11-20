import { Injectable, inject } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';

/**
 * Remembers the previous app URL so back can return exactly where the user
 * came from when Ionic's tab stack has no history (e.g. Discover → competition).
 */
@Injectable({ providedIn: 'root' })
export class BackNavigationService {
  private readonly router = inject(Router);

  private previousUrl: string | null = null;
  private currentUrl: string | null = null;

  constructor() {
    this.currentUrl = this.router.url;
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => {
        const next = event.urlAfterRedirects || event.url;
        // Ignore query-only changes (e.g. competition tab switches) so back
        // still returns to the page the user opened this screen from.
        if (this.currentUrl && this.pathOnly(this.currentUrl) !== this.pathOnly(next)) {
          this.previousUrl = this.currentUrl;
        }
        this.currentUrl = next;
      });
  }

  /**
   * Prefer the real previous page; fall back when the app was opened cold
   * on this screen or history is empty.
   */
  href(fallback: string): string {
    const previous = this.previousUrl;
    if (!previous || this.pathOnly(previous) === this.pathOnly(this.currentUrl ?? '')) {
      return fallback;
    }
    return previous;
  }

  private pathOnly(url: string): string {
    const path = url.split('?')[0] ?? url;
    return path.split('#')[0] ?? path;
  }
}
