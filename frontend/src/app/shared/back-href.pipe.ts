import { Pipe, PipeTransform, inject } from '@angular/core';

import { BackNavigationService } from '../core/back-navigation.service';

/** Resolves ion-back-button defaultHref to the exact previous app URL when possible. */
@Pipe({ name: 'backHref', standalone: true, pure: false })
export class BackHrefPipe implements PipeTransform {
  private readonly history = inject(BackNavigationService);

  transform(fallback: string): string {
    return this.history.href(fallback || '/');
  }
}
