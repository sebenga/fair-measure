import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  flushMicrotasks,
  tick,
} from '@angular/core/testing';

import { HOUSE_COMPETITION_AD, type AdCreative } from '../core/ad-break';
import { AdBreakComponent } from './ad-break.component';

describe('AdBreakComponent', () => {
  let fixture: ComponentFixture<AdBreakComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AdBreakComponent] });
  });

  afterEach(() => {
    fixture?.destroy();
  });

  function setup(creative?: AdCreative): AdBreakComponent {
    fixture = TestBed.createComponent(AdBreakComponent);
    if (creative) fixture.componentRef.setInput('creative', creative);
    fixture.detectChanges();
    flushMicrotasks();
    return fixture.componentInstance;
  }

  it('shows the 30 second house ad with no skip control', fakeAsync(() => {
    setup();
    const root = fixture.nativeElement as HTMLElement;
    expect(document.body.contains(root)).toBeTrue();
    expect(root.textContent).toContain('Advertisement');
    expect(root.textContent).toContain('Fair Measure');
    expect(root.textContent).toContain('Every point, counted in the open.');
    expect(root.textContent).toContain('0:30');
    expect(root.textContent).toContain('Competition opens in');
    expect(root.querySelector('button')).toBeNull();
    expect(root.querySelector('[data-ad-break]')?.getAttribute('role')).toBe('dialog');

    const link = root.querySelector('a');
    expect(link?.getAttribute('href')).toBe('https://fair-measure.com/');
    expect(link?.getAttribute('target')).toBe('_blank');
    expect(link?.getAttribute('rel')).toContain('noopener');
    discardPeriodicTasks();
  }));

  it('counts down and then finishes, and a click-through does not finish it early', fakeAsync(() => {
    const creative: AdCreative = { ...HOUSE_COMPETITION_AD, durationSeconds: 3, href: 'https://fair-measure.com/' };
    const component = setup(creative);
    let finished = 0;
    component.finished.subscribe(() => {
      finished += 1;
    });

    expect(fixture.nativeElement.textContent).toContain('0:03');
    const link = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    link.addEventListener('click', (event) => event.preventDefault());
    link.click();
    expect(finished).toBe(0);

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    expect(finished).toBe(0);

    tick(1000);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('0:02');
    expect(finished).toBe(0);

    tick(2000);
    fixture.detectChanges();
    expect(finished).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('0:00');
  }));

  it('renders an image creative in the same countdown slot', fakeAsync(() => {
    const creative: AdCreative = {
      ...HOUSE_COMPETITION_AD,
      durationSeconds: 5,
      media: { type: 'image', src: 'assets/landing/hero.jpg', alt: 'Sponsor board' },
    };
    setup(creative);
    const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    expect(image.getAttribute('src')).toContain('hero.jpg');
    expect(image.alt).toBe('Sponsor board');
    expect(fixture.nativeElement.querySelector('.mark')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('0:05');
    discardPeriodicTasks();
  }));

  it('renders a muted looping video creative', fakeAsync(() => {
    const creative: AdCreative = {
      ...HOUSE_COMPETITION_AD,
      durationSeconds: 4,
      media: { type: 'video', src: 'assets/landing/hero.jpg', poster: 'assets/landing/hero.jpg' },
    };
    setup(creative);
    const video = fixture.nativeElement.querySelector('video') as HTMLVideoElement;
    expect(video.getAttribute('src')).toContain('hero.jpg');
    expect(video.muted).toBeTrue();
    expect(video.autoplay).toBeTrue();
    expect(video.loop).toBeTrue();
    expect(video.hasAttribute('playsinline')).toBeTrue();
    expect(video.getAttribute('poster')).toContain('hero.jpg');
    discardPeriodicTasks();
  }));

  it('marks reduced motion so the decorative animation can stop', fakeAsync(() => {
    spyOn(window, 'matchMedia').and.returnValue({
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() {
        return false;
      },
    } as MediaQueryList);
    setup({ ...HOUSE_COMPETITION_AD, durationSeconds: 2 });
    expect(fixture.nativeElement.classList.contains('is-reduced-motion')).toBeTrue();
    discardPeriodicTasks();
  }));
});
