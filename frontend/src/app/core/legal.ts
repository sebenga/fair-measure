/**
 * Fair Measure's legal notices, disclaimers and footer.
 *
 * Every [bracketed] value is a placeholder that must be filled in before the notices are relied on;
 * the legal page marks them so none is missed. Have a South African attorney review the text.
 */

export const LEGAL = {
  owner: 'Keneths House',
  product: 'Fair Measure',
  website: 'https://fairmeasure-v2.onrender.com',
  lastUpdated: '11 November 2026',
  year: 2026,
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
      'This website and the Fair Measure application ("the Service") are owned and operated by Keneths House [(Pty) Ltd], registration number [CIPC reg. no.], a company incorporated in the Republic of South Africa.',
      [
        { label: 'Registered/physical address', text: '[address]' },
        { label: 'Email', text: '[legal@…] · Phone: [number]' },
        { label: 'Directors', text: '[names]' },
        { label: 'VAT number (if registered)', text: '[number]' },
        { label: 'Information Officer (POPIA)', text: '[name, email]' },
      ],
      'These disclosures are made in terms of section 43 of the Electronic Communications and Transactions Act 25 of 2002 (ECTA).',
    ],
  },
  {
    id: 'copyright',
    title: 'Intellectual Property & Copyright',
    body: [
      '© 2026 Keneths House. All rights reserved.',
      'All content, software, source code, designs, logos, the name "Fair Measure", scoring engines, presets, text, graphics and databases on this Service are the property of Keneths House or its licensors and are protected by the South African Copyright Act 98 of 1978, the Trade Marks Act 194 of 1993, and international treaties including the Berne Convention, the TRIPS Agreement and the WIPO Copyright Treaty.',
      'You may not copy, reproduce, modify, distribute, reverse-engineer, scrape, frame or create derivative works from any part of the Service without our prior written consent, except as allowed by law (e.g. fair dealing).',
      '"Fair Measure" and its logo are trademarks of Keneths House [registered / pending registration under application no. …]. Third-party names and marks (e.g. FIFA, World Rugby, FEI, IOC, Premier League) belong to their respective owners and are used only to describe compatibility with their published rules. Fair Measure is not affiliated with, endorsed by, or sponsored by any sports federation or governing body.',
    ],
  },
  {
    id: 'content',
    title: 'User Content',
    body: [
      'You keep ownership of the data you enter (teams, players, scores, results). By submitting it you grant Keneths House a non-exclusive, royalty-free, worldwide licence to host, process and display it solely to operate and improve the Service. You confirm you have the right to upload it, including consent from any person whose information you add.',
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
      'To the maximum extent permitted by law, Keneths House, its directors, employees and agents are not liable for any direct, indirect, incidental, special or consequential loss or damage (including loss of data, profit or reputation) arising from your use of, or inability to use, the Service.',
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
          text: 'profiles of persons under 18 may only be created with consent of a parent or guardian (POPIA s35). Organisers (schools, clubs) are responsible for obtaining this consent.',
        },
        {
          label: 'Sharing',
          text: 'only with service providers who host and run the Service (e.g. Render, hosted in Frankfurt, Germany), under appropriate safeguards (POPIA s72 cross-border transfers). We do not sell personal information.',
        },
        {
          label: 'Your rights',
          text: 'access, correction, deletion, objection, and to complain to the Information Regulator (https://inforegulator.org.za, complaints.IR@inforegulator.org.za).',
        },
        {
          label: 'Security',
          text: 'we take reasonable technical and organisational measures (POPIA s19) but no system is fully secure.',
        },
        { label: 'Retention', text: 'kept only as long as needed for the purpose or as required by law.' },
        {
          label: 'Cookies',
          text: 'we use essential cookies/local storage for login and settings. [List analytics cookies if any.]',
        },
      ],
      'Contact our Information Officer at [email] for any privacy request.',
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
      'We may change, suspend or discontinue any part of the Service at any time. We may update these notices; the "Last updated" date shows the current version. Continued use means you accept the updated terms.',
    ],
  },
  {
    id: 'law',
    title: 'Governing Law & Jurisdiction',
    body: [
      "These terms are governed by the laws of the Republic of South Africa. You consent to the jurisdiction of the South African courts [Magistrate's Court / High Court, Gauteng Division] subject to any consumer's right to approach a court or forum of their choice under the CPA. If any provision is found invalid, the rest remains in force.",
    ],
  },
  {
    id: 'contact',
    title: 'Contact',
    body: ['Keneths House · [address] · [email] · [phone]'],
  },
];

export type LegalPiece = { kind: 'text' | 'blank' | 'link'; value: string };

/** Splits a line so placeholders can be marked and web addresses linked. */
export function legalPieces(text: string): LegalPiece[] {
  return text
    .split(/(\[[^\]]*\]|https?:\/\/[^\s,)]+)/)
    .filter(Boolean)
    .map((value) => ({
      kind: value.startsWith('[') ? 'blank' : /^https?:\/\//.test(value) ? 'link' : 'text',
      value,
    }));
}
