import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormArray,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCheckbox,
  IonContent,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonList,
  IonNote,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { trashOutline } from 'ionicons/icons';

import { CompanyLegalService } from '../../core/company-legal.service';
import { extractErrorMessage } from '../../core/error-message';
import { SA_PROVINCES, type CompanyLegal } from '../../core/legal';
import { BackHrefPipe } from '../../shared/back-href.pipe';

function cipcValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value || '').trim();
  if (!value) return { required: true };
  return /^\d{4}\/\d{6}\/\d{2}$/.test(value) ? null : { cipc: true };
}

function vatValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value || '').trim();
  if (!value) return null;
  return /^4\d{9}$/.test(value) ? null : { vat: true };
}

function saPhoneValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value || '').trim().replace(/\s+/g, '');
  if (!value) return { required: true };
  return /^\+27\d{9}$/.test(value) ? null : { phone: true };
}

@Component({
  selector: 'fm-company-legal',
  standalone: true,
  imports: [
    BackHrefPipe,
    ReactiveFormsModule,
    RouterLink,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonList,
    IonItem,
    IonInput,
    IonSelect,
    IonSelectOption,
    IonCheckbox,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="'/tabs/platform' | backHref" />
        </ion-buttons>
        <ion-title>Company Legal Details</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="center"><ion-spinner /></div>
      } @else {
        <form [formGroup]="form" (ngSubmit)="save()" class="page">
          <p class="hint">
            These values fill the site footer, the public /legal disclosure, Terms and Privacy tokens,
            and Organization JSON-LD. Only platform admins can edit them.
          </p>

          <h3 class="fm-section-title">Company identity</h3>
          <ion-list inset="true">
            <ion-item>
              <ion-input label="Legal name" labelPlacement="stacked" formControlName="legal_name"
                placeholder="Example (Pty) Ltd" />
            </ion-item>
            @if (showError('legal_name')) {
              <ion-note color="danger" role="alert" class="err">Registered company name is required.</ion-note>
            }
            <ion-item>
              <ion-input label="Trading name (optional)" labelPlacement="stacked" formControlName="trading_name" />
            </ion-item>
            <ion-item>
              <ion-input label="Registration number (CIPC)" labelPlacement="stacked"
                formControlName="registration_number" placeholder="YYYY/NNNNNN/NN" />
            </ion-item>
            @if (showError('registration_number')) {
              <ion-note color="danger" role="alert" class="err">Use CIPC format YYYY/NNNNNN/NN.</ion-note>
            }
            <ion-item>
              <ion-input label="VAT number (optional)" labelPlacement="stacked" formControlName="vat_number"
                placeholder="4XXXXXXXXX" />
            </ion-item>
            @if (showError('vat_number')) {
              <ion-note color="danger" role="alert" class="err">10 digits starting with 4.</ion-note>
            }
            <ion-item>
              <ion-input label="Product / brand" labelPlacement="stacked" formControlName="product" />
            </ion-item>
            <ion-item>
              <ion-input label="Website" labelPlacement="stacked" formControlName="website" type="url" />
            </ion-item>
          </ion-list>

          <h3 class="fm-section-title">Directors</h3>
          <ion-list inset="true" formArrayName="directors">
            @for (ctrl of directors.controls; track $index; let i = $index) {
              <ion-item>
                <ion-input [formControlName]="i" [label]="'Director ' + (i + 1)" labelPlacement="stacked" />
                <ion-button slot="end" fill="clear" color="danger" type="button"
                  [disabled]="directors.length === 1" (click)="removeDirector(i)" aria-label="Remove director">
                  <ion-icon slot="icon-only" name="trash-outline" />
                </ion-button>
              </ion-item>
            }
          </ion-list>
          @if (directors.invalid && (directors.touched || submitted())) {
            <ion-note color="danger" role="alert" class="err">Add at least one director.</ion-note>
          }
          <ion-button fill="outline" size="small" type="button" class="add" (click)="addDirector()">
            Add director
          </ion-button>

          <h3 class="fm-section-title">Contact &amp; address</h3>
          <ion-list inset="true">
            <ion-item>
              <ion-input label="Email" labelPlacement="stacked" formControlName="email" type="email" />
            </ion-item>
            @if (showError('email')) {
              <ion-note color="danger" role="alert" class="err">Enter a valid email.</ion-note>
            }
            <ion-item>
              <ion-input label="Phone (+27…)" labelPlacement="stacked" formControlName="phone"
                placeholder="+27821234567" />
            </ion-item>
            @if (showError('phone')) {
              <ion-note color="danger" role="alert" class="err">Use +27 followed by 9 digits.</ion-note>
            }
          </ion-list>

          <h4 class="sub">Physical address</h4>
          <ion-list inset="true" formGroupName="physical_address">
            <ion-item>
              <ion-input label="Street" labelPlacement="stacked" formControlName="street" />
            </ion-item>
            <ion-item>
              <ion-input label="Suburb" labelPlacement="stacked" formControlName="suburb" />
            </ion-item>
            <ion-item>
              <ion-input label="City" labelPlacement="stacked" formControlName="city" />
            </ion-item>
            <ion-item>
              <ion-select label="Province" labelPlacement="stacked" formControlName="province" interface="popover">
                @for (province of provinces; track province) {
                  <ion-select-option [value]="province">{{ province }}</ion-select-option>
                }
              </ion-select>
            </ion-item>
            <ion-item>
              <ion-input label="Postal code" labelPlacement="stacked" formControlName="postal_code" />
            </ion-item>
          </ion-list>

          <ion-list inset="true">
            <ion-item>
              <ion-checkbox labelPlacement="end" formControlName="postal_same_as_physical">
                Postal address same as physical
              </ion-checkbox>
            </ion-item>
          </ion-list>

          @if (!form.controls.postal_same_as_physical.value) {
            <h4 class="sub">Postal address</h4>
            <ion-list inset="true" formGroupName="postal_address">
              <ion-item>
                <ion-input label="Street" labelPlacement="stacked" formControlName="street" />
              </ion-item>
              <ion-item>
                <ion-input label="Suburb" labelPlacement="stacked" formControlName="suburb" />
              </ion-item>
              <ion-item>
                <ion-input label="City" labelPlacement="stacked" formControlName="city" />
              </ion-item>
              <ion-item>
                <ion-select label="Province" labelPlacement="stacked" formControlName="province" interface="popover">
                  @for (province of provinces; track province) {
                    <ion-select-option [value]="province">{{ province }}</ion-select-option>
                  }
                </ion-select>
              </ion-item>
              <ion-item>
                <ion-input label="Postal code" labelPlacement="stacked" formControlName="postal_code" />
              </ion-item>
            </ion-list>
          }

          <h3 class="fm-section-title">Privacy (POPIA)</h3>
          <ion-list inset="true">
            <ion-item>
              <ion-input label="Information officer name" labelPlacement="stacked"
                formControlName="information_officer_name" />
            </ion-item>
            <ion-item>
              <ion-input label="Information officer email" labelPlacement="stacked"
                formControlName="information_officer_email" type="email" />
            </ion-item>
            <ion-item>
              <ion-input label="Privacy policy effective date" labelPlacement="stacked"
                formControlName="privacy_policy_effective_date" type="date" />
            </ion-item>
          </ion-list>

          <h3 class="fm-section-title">Copyright &amp; IP</h3>
          <ion-list inset="true">
            <ion-item>
              <ion-input label="Copyright holder" labelPlacement="stacked" formControlName="copyright_holder" />
            </ion-item>
            <ion-item>
              <ion-input label="Copyright start year" labelPlacement="stacked" type="number"
                formControlName="copyright_start_year" />
            </ion-item>
          </ion-list>
          <p class="hint">Displayed as {{ copyrightPreview() }}.</p>

          <h4 class="sub">Trademarks (optional)</h4>
          <ion-list inset="true" formArrayName="trademarks">
            @for (row of trademarks.controls; track $index; let i = $index) {
              <div [formGroupName]="i" class="tm-row">
                <ion-item>
                  <ion-input label="Mark" labelPlacement="stacked" formControlName="mark" />
                </ion-item>
                <ion-item>
                  <ion-select label="Status" labelPlacement="stacked" formControlName="status" interface="popover">
                    <ion-select-option value="registered">Registered (®)</ion-select-option>
                    <ion-select-option value="pending">Pending (™)</ion-select-option>
                  </ion-select>
                </ion-item>
                <ion-button fill="clear" color="danger" type="button" (click)="removeTrademark(i)">
                  Remove
                </ion-button>
              </div>
            }
          </ion-list>
          <ion-button fill="outline" size="small" type="button" class="add" (click)="addTrademark()">
            Add trademark
          </ion-button>

          <h3 class="fm-section-title">Terms</h3>
          <ion-list inset="true">
            <ion-item>
              <ion-input label="Terms effective date" labelPlacement="stacked"
                formControlName="terms_effective_date" type="date" />
            </ion-item>
            <ion-item>
              <ion-input label="Governing law" labelPlacement="stacked" formControlName="governing_law" />
            </ion-item>
          </ion-list>

          @if (formError()) {
            <p class="fm-form-error" role="alert">{{ formError() }}</p>
          }

          <ion-button expand="block" type="submit" [disabled]="saving()">
            @if (saving()) {
              <ion-spinner name="crescent" />
            } @else {
              Save company legal details
            }
          </ion-button>

          <section class="preview" aria-label="Live preview">
            <h3 class="fm-section-title">Footer preview</h3>
            <p class="footer-preview">
              {{ copyrightPreview() }}. All rights reserved.
              @if (preview().legal_name) {
                {{ preview().legal_name }}
                @if (preview().registration_number) {
                  (Reg. {{ preview().registration_number }})
                }
                @if (preview().vat_number) {
                  · VAT {{ preview().vat_number }}
                }.
              }
              {{ preview().product || 'Fair Measure' }} is owned and operated in South Africa.
            </p>
            <h3 class="fm-section-title">/legal disclosure preview</h3>
            <dl class="disclosure">
              <div><dt>Legal name</dt><dd>{{ preview().legal_name || '—' }}</dd></div>
              <div><dt>Trading name</dt><dd>{{ preview().trading_name || '—' }}</dd></div>
              <div><dt>Registration</dt><dd>{{ preview().registration_number || '—' }}</dd></div>
              <div><dt>VAT</dt><dd>{{ preview().vat_number || '—' }}</dd></div>
              <div><dt>Directors</dt><dd>{{ previewDirectors() }}</dd></div>
              <div><dt>Email</dt><dd>{{ preview().email || '—' }}</dd></div>
              <div><dt>Phone</dt><dd>{{ preview().phone || '—' }}</dd></div>
              <div><dt>Website</dt><dd>{{ preview().website || '—' }}</dd></div>
              <div><dt>Physical address</dt><dd>{{ previewAddress() }}</dd></div>
              <div>
                <dt>Information officer</dt>
                <dd>{{ preview().information_officer_name || '—' }} · {{ preview().information_officer_email || '—' }}</dd>
              </div>
              <div><dt>Governing law</dt><dd>{{ preview().governing_law || '—' }}</dd></div>
            </dl>
            <p class="hint">
              Open the full page at
              <a routerLink="/legal">/legal</a>
              after saving.
            </p>
          </section>
        </form>
      }
    </ion-content>
  `,
  styles: `
    .page {
      padding-bottom: 48px;
    }
    .center {
      display: grid;
      place-items: center;
      padding: 64px 0;
    }
    .hint {
      margin: 12px 20px;
      color: var(--ion-color-medium);
      font-size: 0.9rem;
      line-height: 1.45;
    }
    .fm-section-title {
      margin: 20px 20px 8px;
    }
    .sub {
      margin: 8px 20px;
      font-size: 0.95rem;
    }
    .add {
      margin: 0 16px 12px;
    }
    .err {
      display: block;
      margin: 0 20px 8px;
    }
    .tm-row {
      margin-bottom: 8px;
    }
    .preview {
      margin-top: 28px;
      border-top: 1px solid var(--ion-color-light-shade);
      padding-top: 8px;
    }
    .disclosure {
      margin: 0 20px;
      display: grid;
      gap: 10px;
    }
    .disclosure div {
      display: grid;
      gap: 2px;
    }
    .disclosure dt {
      font-size: 0.75rem;
      color: var(--ion-color-medium);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .disclosure dd {
      margin: 0;
      font-size: 0.95rem;
    }
    .fm-form-error {
      margin: 12px 20px;
      color: var(--ion-color-danger);
    }
    .footer-preview {
      margin: 0 20px;
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--ion-color-light);
      color: var(--ion-color-medium);
      font-size: 0.82rem;
      line-height: 1.5;
    }
  `,
})
export class CompanyLegalPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly legal = inject(CompanyLegalService);
  private readonly toasts = inject(ToastController);

  constructor() {
    addIcons({ trashOutline });
  }

  readonly provinces = SA_PROVINCES;
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly submitted = signal(false);
  readonly formError = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    product: ['Fair Measure', Validators.required],
    legal_name: ['', Validators.required],
    trading_name: [''],
    registration_number: ['', [cipcValidator]],
    vat_number: ['', [vatValidator]],
    directors: this.fb.nonNullable.array([this.fb.nonNullable.control('', Validators.required)]),
    email: ['', [Validators.required, Validators.email]],
    phone: ['', [saPhoneValidator]],
    website: ['https://fairmeasure-v2.onrender.com', Validators.required],
    physical_address: this.fb.nonNullable.group({
      street: ['', Validators.required],
      suburb: ['', Validators.required],
      city: ['', Validators.required],
      province: ['', Validators.required],
      postal_code: ['', Validators.required],
    }),
    postal_same_as_physical: [true],
    postal_address: this.fb.nonNullable.group({
      street: [''],
      suburb: [''],
      city: [''],
      province: [''],
      postal_code: [''],
    }),
    information_officer_name: ['', Validators.required],
    information_officer_email: ['', [Validators.required, Validators.email]],
    privacy_policy_effective_date: ['', Validators.required],
    copyright_holder: ['', Validators.required],
    copyright_start_year: [new Date().getFullYear(), Validators.required],
    trademarks: this.fb.nonNullable.array([] as ReturnType<CompanyLegalPage['trademarkGroup']>[]),
    terms_effective_date: ['', Validators.required],
    governing_law: ['Republic of South Africa', Validators.required],
  });

  readonly preview = signal(this.form.getRawValue() as unknown as CompanyLegal);
  readonly copyrightPreview = computed(() => {
    const start = Number(this.preview().copyright_start_year) || new Date().getFullYear();
    const year = new Date().getFullYear();
    const range = start >= year ? String(year) : `${start}–${year}`;
    const holder = this.preview().copyright_holder || this.preview().legal_name || '…';
    return `© ${range} ${holder}`;
  });

  get directors(): FormArray {
    return this.form.controls.directors;
  }

  get trademarks(): FormArray {
    return this.form.controls.trademarks;
  }

  ngOnInit(): void {
    this.form.valueChanges.subscribe(() => {
      this.preview.set(this.form.getRawValue() as unknown as CompanyLegal);
      const holder = this.form.controls.copyright_holder;
      const legalName = this.form.controls.legal_name.value;
      if (!holder.dirty && legalName && !holder.value) {
        holder.setValue(legalName, { emitEvent: false });
      }
    });

    this.legal.refresh().subscribe({
      next: (row) => {
        this.patchForm(row);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  showError(controlName: string): boolean {
    const control = this.form.get(controlName);
    return !!control && control.invalid && (control.touched || this.submitted());
  }

  addDirector(): void {
    this.directors.push(this.fb.nonNullable.control('', Validators.required));
  }

  removeDirector(index: number): void {
    if (this.directors.length > 1) this.directors.removeAt(index);
  }

  trademarkGroup(mark = '', status: 'registered' | 'pending' = 'pending') {
    return this.fb.nonNullable.group({
      mark: [mark, Validators.required],
      status: [status as 'registered' | 'pending', Validators.required],
    });
  }

  addTrademark(): void {
    this.trademarks.push(this.trademarkGroup());
  }

  removeTrademark(index: number): void {
    this.trademarks.removeAt(index);
  }

  previewDirectors(): string {
    return (this.preview().directors || []).filter(Boolean).join(', ') || '—';
  }

  previewAddress(): string {
    const a = this.preview().physical_address;
    if (!a) return '—';
    return [a.street, a.suburb, a.city, a.province, a.postal_code].filter(Boolean).join(', ') || '—';
  }

  save(): void {
    this.submitted.set(true);
    this.formError.set(null);
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) {
      this.formError.set('Fix the highlighted fields before saving.');
      return;
    }
    const raw = this.form.getRawValue();
    const body: Partial<CompanyLegal> = {
      ...raw,
      directors: raw.directors.map((name) => name.trim()).filter(Boolean),
      trademarks: raw.trademarks
        .map((row) => ({ mark: row.mark.trim(), status: row.status }))
        .filter((row) => row.mark),
      phone: raw.phone.replace(/\s+/g, ''),
      copyright_holder: raw.copyright_holder || raw.legal_name,
      copyright_start_year: Number(raw.copyright_start_year),
    };
    this.saving.set(true);
    this.legal.save(body).subscribe({
      next: async () => {
        this.saving.set(false);
        this.submitted.set(false);
        const toast = await this.toasts.create({
          message: 'Company legal details saved.',
          color: 'success',
          duration: 2200,
        });
        await toast.present();
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        this.formError.set(extractErrorMessage(err, 'Could not save company legal details.'));
      },
    });
  }

  private patchForm(row: CompanyLegal): void {
    while (this.directors.length) this.directors.removeAt(0);
    const directors = row.directors?.length ? row.directors : [''];
    for (const name of directors) {
      this.directors.push(this.fb.nonNullable.control(name, Validators.required));
    }
    while (this.trademarks.length) this.trademarks.removeAt(0);
    for (const mark of row.trademarks || []) {
      this.trademarks.push(this.trademarkGroup(mark.mark, mark.status));
    }
    this.form.patchValue({
      product: row.product || 'Fair Measure',
      legal_name: row.legal_name || '',
      trading_name: row.trading_name || '',
      registration_number: row.registration_number || '',
      vat_number: row.vat_number || '',
      email: row.email || '',
      phone: row.phone || '',
      website: row.website || 'https://fairmeasure-v2.onrender.com',
      physical_address: {
        street: row.physical_address?.street || '',
        suburb: row.physical_address?.suburb || '',
        city: row.physical_address?.city || '',
        province: row.physical_address?.province || '',
        postal_code: row.physical_address?.postal_code || '',
      },
      postal_same_as_physical: row.postal_same_as_physical !== false,
      postal_address: {
        street: row.postal_address?.street || '',
        suburb: row.postal_address?.suburb || '',
        city: row.postal_address?.city || '',
        province: row.postal_address?.province || '',
        postal_code: row.postal_address?.postal_code || '',
      },
      information_officer_name: row.information_officer_name || '',
      information_officer_email: row.information_officer_email || '',
      privacy_policy_effective_date: row.privacy_policy_effective_date || '',
      copyright_holder: row.copyright_holder || row.legal_name || '',
      copyright_start_year: row.copyright_start_year || new Date().getFullYear(),
      terms_effective_date: row.terms_effective_date || '',
      governing_law: row.governing_law || 'Republic of South Africa',
    });
    this.preview.set(this.form.getRawValue() as unknown as CompanyLegal);
  }
}
