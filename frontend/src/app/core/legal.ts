/**
 * Fair Measure's legal notices, disclaimers and footer.
 *
 * Identity and contact values come from Company Legal Details (API). Tokens like
 * {{legalName}} and remaining [bracketed] placeholders are filled by legalPieces
 * / fillLegalText. Do not hardcode company values here once the form is in use.
 */

export interface CompanyLegal {
  id?: string;
  product: string;
  legal_name: string;
  trading_name: string;
  registration_number: string;
  vat_number: string;
  directors: string[];
  physical_address: {
    street: string;
    suburb: string;
    city: string;
    province: string;
    postal_code: string;
  };
  postal_address: {
    street: string;
    suburb: string;
    city: string;
    province: string;
    postal_code: string;
  };
  postal_same_as_physical: boolean;
  email: string;
  phone: string;
  website: string;
  information_officer_name: string;
  information_officer_email: string;
  privacy_policy_effective_date: string | null;
  copyright_holder: string;
  copyright_start_year: number;
  copyright_year_range?: string;
  trademarks: Array<{ mark: string; status: 'registered' | 'pending' }>;
  trademark_labels?: string[];
  terms_effective_date: string | null;
  governing_law: string;
  formatted_physical_address?: string;
  formatted_postal_address?: string;
  updated_at?: string;
}

/** Fallback identity until the public GET returns (or if it fails). */
export const LEGAL_FALLBACK: CompanyLegal = {
  product: 'Fair Measure',
  legal_name: '',
  trading_name: '',
  registration_number: '',
  vat_number: '',
  directors: [],
  physical_address: { street: '', suburb: '', city: '', province: '', postal_code: '' },
  postal_address: { street: '', suburb: '', city: '', province: '', postal_code: '' },
  postal_same_as_physical: true,
  email: '',
  phone: '',
  website: 'https://fairmeasure-v2.onrender.com',
  information_officer_name: '',
  information_officer_email: '',
  privacy_policy_effective_date: null,
  copyright_holder: '',
  copyright_start_year: new Date().getFullYear(),
  trademarks: [],
  terms_effective_date: null,
  governing_law: 'Republic of South Africa',
};

/** @deprecated Prefer CompanyLegalService.snapshot() — kept for gradual migration. */
export const LEGAL = {
  get owner() {
    return LEGAL_FALLBACK.legal_name || LEGAL_FALLBACK.product;
  },
  get product() {
    return LEGAL_FALLBACK.product;
  },
  get website() {
    return LEGAL_FALLBACK.website;
  },
  get lastUpdated() {
    return LEGAL_FALLBACK.terms_effective_date || LEGAL_FALLBACK.privacy_policy_effective_date || '';
  },
  get year() {
    return new Date().getFullYear();
  },
};

export interface LegalPoint {
  label?: string;
  text: string;
}

export interface LegalSection {
  id: string;
  title: string;
  body: Array<string | LegalPoint[]>;
}

export const LEGAL_SECTIONS: LegalSection[] = [
  {
    id: 'ownership',
    title: 'Ownership & Legal Notice (ECTA s43 disclosure)',
    body: [
      'This website and the {{product}} application ("the Service") are owned and operated by {{legalName}}, registration number {{registrationNumber}}, a company incorporated in the Republic of South Africa.',
      [
        { label: 'Registered/physical address', text: '{{physicalAddress}}' },
        { label: 'Email', text: '{{email}} · Phone: {{phone}}' },
        { label: 'Directors', text: '{{directors}}' },
        { label: 'VAT number (if registered)', text: '{{vatNumber}}' },
        { label: 'Information Officer (POPIA)', text: '{{informationOfficerName}}, {{informationOfficerEmail}}' },
        { label: 'Trading name', text: '{{tradingName}}' },
        { label: 'Website', text: '{{website}}' },
        { label: 'Postal address', text: '{{postalAddress}}' },
      ],
      'These disclosures are made in terms of section 43 of the Electronic Communications and Transactions Act 25 of 2002 (ECTA).',
    ],
  },
  {
    id: 'copyright',
    title: 'Intellectual Property & Copyright',
    body: [
      '© {{copyrightYearRange}} {{copyrightHolder}}. All rights reserved.',
      'All content, software, source code, designs, logos, the name "{{product}}", scoring engines, presets, text, graphics and databases on this Service are the property of {{copyrightHolder}} or its licensors and are protected by the South African Copyright Act 98 of 1978, the Trade Marks Act 194 of 1993, and international treaties including the Berne Convention, the TRIPS Agreement and the WIPO Copyright Treaty.',
      'You may not copy, reproduce, modify, distribute, reverse-engineer, scrape, frame or create derivative works from any part of the Service without our prior written consent, except as allowed by law (e.g. fair dealing).',
      '"{{product}}" and its logo are trademarks of {{copyrightHolder}}{{trademarksSuffix}}. Third-party names and marks (e.g. FIFA, World Rugby, FEI, IOC, Premier League) belong to their respective owners and are used only to describe compatibility with their published rules. {{product}} is not affiliated with, endorsed by, or sponsored by any sports federation or governing body.',
    ],
  },
  {
    id: 'content',
    title: 'User Content',
    body: [
      'You keep ownership of the data you enter (teams, players, scores, results). By submitting it you grant {{legalName}} a non-exclusive, royalty-free, worldwide licence to host, process and display it solely to operate and improve the Service. You confirm you have the right to upload it, including consent from any person whose information you add.',
    ],
  },
  {
    id: 'disclaimer',
    title: 'General Disclaimer',
    body: [
      'The Service is provided "as is" and "as available". Scores, rankings, player ratings, fantasy points, scouting data and statistics are calculated from user-entered data and published rules and are for information and entertainment only. We do not guarantee they are accurate, complete or error-free, and they are not official results of any governing body.',
      'Nothing on the Service is professional, financial, betting, medical or legal advice. Do not rely on it for gambling, contracts, selection or employment decisions without independent verification.',
    ],
  },
  {
    id: 'liability',
    title: 'Limitation of Liability',
    body: [
      'To the maximum extent permitted by law, {{legalName}}, its directors, employees and agents are not liable for any direct, indirect, incidental, special or consequential loss or damage (including loss of data, profit or reputation) arising from your use of, or inability to use, the Service.',
      'Nothing in these terms limits liability that cannot lawfully be limited, including under the Consumer Protection Act 68 of 2008 (CPA) or for gross negligence or wilful misconduct. Where the CPA applies, these terms are subject to your rights under it, and any provision that conflicts with the CPA applies only to the extent the law allows (CPA s49 notice: please pay special attention to sections 4, 5 and 6).',
    ],
  },
  {
    id: 'privacy',
    title: 'Privacy & Data Protection (POPIA, and GDPR where applicable)',
    body: [
      'We process personal information in accordance with the Protection of Personal Information Act 4 of 2013 (POPIA). Where users in the EU/UK use the Service, we apply the principles of the GDPR / UK GDPR.',
      [
        {
          label: 'What we collect',
          text: 'account details (name, email), competition data, player profiles and stats, device and usage logs.',
        },
        { label: 'Why', text: 'to provide the Service, run competitions, secure accounts and improve features.' },
        {
          label: 'Children',
          text: 'profiles of persons under 18 may only be created with consent of a parent or guardian (POPIA s35). Organisers (schools, clubs) are responsible for obtaining this consent. Match video, AI shirt-number identification and public clips for minors require guardian consent; without it we blur or exclude that player and do not create AI stats for them.',
        },
        {
          label: 'Match video & AI camera',
          text: 'Recording is off by default and needs an organiser recording policy plus player/guardian acceptance (or refusal) on the profile. Identification is by shirt number and submitted lineup only — we do not use facial recognition. Raw video is deleted after a configurable retention period (default 30 days). Confirmed clips are kept only with consent. Players may request deletion.',
        },
        {
          label: 'Sharing',
          text: 'only with service providers who host and run the Service (e.g. Render, hosted in Frankfurt, Germany; optional external GPU providers for AI), under appropriate safeguards (POPIA s72 cross-border transfers). We do not sell personal information.',
        },
        {
          label: 'Your rights',
          text: 'access, correction, deletion, objection, and to complain to the Information Regulator (https://inforegulator.org.za, complaints.IR@inforegulator.org.za).',
        },
        {
          label: 'Security',
          text: 'we take reasonable technical and organisational measures (POPIA s19) but no system is fully secure.',
        },
        {
          label: 'Retention',
          text: 'kept only as long as needed for the purpose or as required by law. Raw match video defaults to 30 days unless configured otherwise.',
        },
        {
          label: 'Cookies',
          text: 'we use essential cookies/local storage for login and settings. [List analytics cookies if any.]',
        },
      ],
      'Contact our Information Officer at {{informationOfficerEmail}} for any privacy request. Privacy policy effective {{privacyPolicyEffectiveDate}}.',
    ],
  },
  {
    id: 'acceptable-use',
    title: 'Acceptable Use',
    body: [
      'You must not: break any law; upload unlawful, defamatory, hateful or infringing content; impersonate others; attempt to hack, overload or disrupt the Service; scrape data; or use it for unlawful gambling. Offences under the Cybercrimes Act 19 of 2020 will be reported to authorities. We may suspend or delete accounts that breach these rules.',
    ],
  },
  {
    id: 'third-parties',
    title: 'Third-Party Links & Services',
    body: [
      'The Service may link to or rely on third-party sites and services. We are not responsible for their content, availability or privacy practices.',
    ],
  },
  {
    id: 'changes',
    title: 'Availability & Changes',
    body: [
      'We may change, suspend or discontinue any part of the Service at any time. We may update these notices; the "Last updated" date shows the current version. Continued use means you accept the updated terms. Terms effective {{termsEffectiveDate}}.',
    ],
  },
  {
    id: 'law',
    title: 'Governing Law & Jurisdiction',
    body: [
      'These terms are governed by the laws of {{governingLaw}}. You consent to the jurisdiction of the South African courts [Magistrate\'s Court / High Court, Gauteng Division] subject to any consumer\'s right to approach a court or forum of their choice under the CPA. If any provision is found invalid, the rest remains in force.',
    ],
  },
  {
    id: 'contact',
    title: 'Contact',
    body: ['{{legalName}} · {{physicalAddress}} · {{email}} · {{phone}}'],
  },
];

export type LegalPiece = { kind: 'text' | 'blank' | 'link'; value: string };

function blank(label: string): string {
  return `[${label}]`;
}

/** Map of {{token}} → display value (empty becomes a [bracket] blank). */
export function legalTokenMap(company: CompanyLegal): Record<string, string> {
  const year = new Date().getFullYear();
  const start = company.copyright_start_year || year;
  const yearRange =
    company.copyright_year_range ||
    (start >= year ? String(year) : `${start}–${year}`);
  const physical =
    company.formatted_physical_address ||
    [
      company.physical_address?.street,
      company.physical_address?.suburb,
      company.physical_address?.city,
      company.physical_address?.province,
      company.physical_address?.postal_code,
    ]
      .filter(Boolean)
      .join(', ');
  const postal =
    company.postal_same_as_physical
      ? physical
      : company.formatted_postal_address ||
        [
          company.postal_address?.street,
          company.postal_address?.suburb,
          company.postal_address?.city,
          company.postal_address?.province,
          company.postal_address?.postal_code,
        ]
          .filter(Boolean)
          .join(', ');
  const marks =
    (company.trademark_labels && company.trademark_labels.length
      ? company.trademark_labels
      : (company.trademarks || []).map((row) => {
          const suffix = row.status === 'registered' ? '®' : '™';
          return `${row.mark}${suffix}`;
        })
    ).join(', ');
  const trademarksSuffix = marks ? ` (${marks})` : '';

  const value = (raw: string | null | undefined, placeholder: string) =>
    (raw || '').trim() || blank(placeholder);

  return {
    product: value(company.product, 'product'),
    legalName: value(company.legal_name, 'legal name'),
    tradingName: value(company.trading_name, 'trading name'),
    registrationNumber: value(company.registration_number, 'CIPC reg. no.'),
    vatNumber: value(company.vat_number, 'VAT number'),
    directors: value((company.directors || []).filter(Boolean).join(', '), 'directors'),
    physicalAddress: value(physical, 'address'),
    postalAddress: value(postal, 'postal address'),
    email: value(company.email, 'email'),
    phone: value(company.phone, 'phone'),
    website: value(company.website, 'website'),
    informationOfficerName: value(company.information_officer_name, 'information officer'),
    informationOfficerEmail: value(company.information_officer_email, 'information officer email'),
    privacyPolicyEffectiveDate: value(company.privacy_policy_effective_date, 'privacy effective date'),
    copyrightHolder: value(company.copyright_holder || company.legal_name, 'copyright holder'),
    copyrightYearRange: yearRange,
    trademarksSuffix,
    trademarks: value(marks, 'trademarks'),
    termsEffectiveDate: value(company.terms_effective_date, 'terms effective date'),
    governingLaw: value(company.governing_law, 'governing law'),
  };
}

/** Replace {{tokens}} using company legal details. */
export function fillLegalText(text: string, company: CompanyLegal): string {
  const tokens = legalTokenMap(company);
  return text.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key: string) => {
    return tokens[key] ?? blank(key);
  });
}

/** Splits a line so placeholders can be marked and web addresses linked. */
export function legalPieces(text: string, company?: CompanyLegal): LegalPiece[] {
  const filled = company ? fillLegalText(text, company) : text;
  return filled
    .split(/(\[[^\]]*\]|https?:\/\/[^\s,)]+)/)
    .filter(Boolean)
    .map((value) => ({
      kind: value.startsWith('[') ? 'blank' : /^https?:\/\//.test(value) ? 'link' : 'text',
      value,
    }));
}

export const SA_PROVINCES = [
  'Eastern Cape',
  'Free State',
  'Gauteng',
  'KwaZulu-Natal',
  'Limpopo',
  'Mpumalanga',
  'North West',
  'Northern Cape',
  'Western Cape',
] as const;
