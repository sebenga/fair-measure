import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { catchError, of, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { CompanyLegal, LEGAL_FALLBACK } from './legal';

@Injectable({ providedIn: 'root' })
export class CompanyLegalService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  private readonly companySignal = signal<CompanyLegal>({ ...LEGAL_FALLBACK });
  private loaded = false;

  readonly company = this.companySignal.asReadonly();
  readonly displayName = computed(
    () => this.companySignal().legal_name || this.companySignal().product || 'Fair Measure',
  );
  readonly copyrightLine = computed(() => {
    const c = this.companySignal();
    const year = new Date().getFullYear();
    const start = c.copyright_start_year || year;
    const range = c.copyright_year_range || (start >= year ? String(year) : `${start}–${year}`);
    const holder = c.copyright_holder || c.legal_name || c.product;
    return `© ${range} ${holder}. All rights reserved.`;
  });

  snapshot(): CompanyLegal {
    return this.companySignal();
  }

  /** Load once for footers and the public legal page. Safe if the request fails. */
  ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    this.http
      .get<CompanyLegal>(`${this.base}/legal/company`)
      .pipe(
        catchError(() => of(null)),
        tap((row) => {
          if (row) this.companySignal.set(this.normalize(row));
        }),
      )
      .subscribe();
  }

  refresh() {
    return this.http.get<CompanyLegal>(`${this.base}/legal/company`).pipe(
      tap((row) => this.companySignal.set(this.normalize(row))),
      catchError(() => {
        return of(this.companySignal());
      }),
    );
  }

  save(body: Partial<CompanyLegal>) {
    return this.http.patch<CompanyLegal>(`${this.base}/platform/admin/legal`, body).pipe(
      tap((row) => this.companySignal.set(this.normalize(row))),
    );
  }

  private normalize(row: CompanyLegal): CompanyLegal {
    return {
      ...LEGAL_FALLBACK,
      ...row,
      directors: row.directors?.length ? [...row.directors] : [],
      trademarks: row.trademarks?.length ? [...row.trademarks] : [],
      physical_address: {
        ...LEGAL_FALLBACK.physical_address,
        ...(row.physical_address || {}),
      },
      postal_address: {
        ...LEGAL_FALLBACK.postal_address,
        ...(row.postal_address || {}),
      },
    };
  }
}
