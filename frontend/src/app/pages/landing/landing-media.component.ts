import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { pauseOutline, playOutline, volumeHighOutline, volumeMuteOutline } from 'ionicons/icons';

const MEDIA = 'assets/landing';

/** Looping match-day clip behind the hero. Muted until the visitor asks for sound. */
@Component({
  selector: 'fm-hero-media',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (motion()) {
      <video
        #clip
        class="media"
        [poster]="poster"
        [muted]="true"
        loop
        autoplay
        playsinline
        preload="auto"
        aria-hidden="true"
        (play)="playing.set(true)"
        (pause)="playing.set(false)"
      >
        <source [src]="clipSrc" type="video/mp4" />
      </video>
    } @else {
      <img class="media" [src]="poster" alt="" width="1280" height="720" />
    }
    <div class="shade" aria-hidden="true"></div>
    @if (motion()) {
      <div class="controls">
        <button type="button" (click)="toggleSound()" [attr.aria-pressed]="!muted()">
          <ion-icon [name]="muted() ? 'volume-mute-outline' : 'volume-high-outline'" aria-hidden="true" />
          {{ muted() ? 'Sound on' : 'Sound off' }}
        </button>
        <button
          type="button"
          class="icon"
          (click)="togglePlay()"
          [attr.aria-label]="playing() ? 'Pause the video' : 'Play the video'"
        >
          <ion-icon [name]="playing() ? 'pause-outline' : 'play-outline'" aria-hidden="true" />
        </button>
      </div>
    }
  `,
  styles: `
    :host {
      position: absolute;
      inset: 0;
      z-index: 0;
      overflow: hidden;
      border-radius: inherit;
      background: #0b1220;
    }
    .media {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .shade {
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, rgb(4 10 22 / 82%) 0%, rgb(4 10 22 / 55%) 45%, rgb(4 10 22 / 10%) 100%),
        linear-gradient(0deg, rgb(4 10 22 / 70%) 0%, transparent 45%);
    }
    .controls {
      position: absolute;
      top: 14px;
      right: 14px;
      z-index: 2;
      display: flex;
      gap: 8px;
    }
    button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 34px;
      padding: 0 12px;
      border: 1px solid rgb(255 255 255 / 35%);
      border-radius: 999px;
      background: rgb(15 23 42 / 55%);
      color: #fff;
      font: inherit;
      font-size: 0.8rem;
      font-weight: 700;
      backdrop-filter: blur(6px);
      cursor: pointer;
    }
    button.icon {
      width: 34px;
      padding: 0;
      justify-content: center;
    }
    ion-icon {
      font-size: 1.05rem;
    }
  `,
})
export class HeroMediaComponent {
  readonly poster = `${MEDIA}/hero.jpg`;
  readonly clipSrc = `${MEDIA}/hero-loop.mp4`;
  readonly muted = signal(true);
  readonly playing = signal(false);
  /** Video only when the visitor allows motion and is not saving data. */
  readonly motion = signal(false);
  private readonly video = viewChild<ElementRef<HTMLVideoElement>>('clip');

  constructor() {
    addIcons({ pauseOutline, playOutline, volumeHighOutline, volumeMuteOutline });
    afterNextRender(() => {
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
        ?.saveData;
      this.motion.set(!reduced && !saveData);
    });
    // Browsers only autoplay silent video, and the muted attribute alone is not
    // reflected onto the element Angular creates.
    effect(() => {
      const video = this.video()?.nativeElement;
      if (!video) return;
      video.muted = true;
      void video.play().catch(() => undefined);
    });
  }

  toggleSound(): void {
    const video = this.video()?.nativeElement;
    if (!video) return;
    const next = !this.muted();
    this.muted.set(next);
    video.muted = next;
    if (!next) {
      video.volume = 0.6;
      void video.play().catch(() => undefined);
    }
  }

  togglePlay(): void {
    const video = this.video()?.nativeElement;
    if (!video) return;
    if (video.paused) {
      void video.play().catch(() => undefined);
    } else {
      video.pause();
    }
  }
}

export interface StorySlide {
  image: string;
  /** Where the photo is, so every kind of community sees itself: suburb, township, rural. */
  place: string;
}

export interface Story {
  slides: StorySlide[];
  /** Optional clip with sound; loads only when the visitor taps play. */
  video?: string;
  tag: string;
  title: string;
  body: string;
}

export const CORPORATE_STORIES: Story[] = [
  {
    slides: [{ image: `${MEDIA}/corp-kpi.jpg`, place: 'Head office' }],
    tag: 'Corporate KPIs',
    title: 'Quarterly KPI review, run like a league',
    body: 'Score teams on your own KPIs — sales, safety, service — and review the table together.',
  },
  {
    slides: [{ image: `${MEDIA}/corp-merch.jpg`, place: 'Club and company kit' }],
    tag: 'Sport & corporate merchandise',
    title: 'Kit and merchandise in your colours',
    body: 'Jerseys, caps, bottles and trophies for staff leagues, clubs and sponsors.',
  },
];

export const GOVERNMENT_STORIES: Story[] = [
  {
    slides: [{ image: `${MEDIA}/gov-cleanup.jpg`, place: 'Suburb' }],
    tag: 'Schools · custom scoring',
    title: 'Neighbourhood clean-up challenge',
    body: 'Points per bag, per street and per recycling type. Classes compete for a cleaner community.',
  },
  {
    slides: [
      { image: `${MEDIA}/hero.jpg`, place: 'Township · ward games' },
      { image: `${MEDIA}/moment-rugby.jpg`, place: 'Town · club league' },
      { image: `${MEDIA}/gov-programme.jpg`, place: 'Provincial finals' },
    ],
    tag: 'National · provincial · local',
    title: 'From ward games to provincial finals',
    body: 'Local leagues feed district, provincial and national programmes, with public tables for residents.',
  },
];

const FADE_EVERY_MS = 4500;

/** Photo cards that fade between places, and can play a short clip with sound on request. */
@Component({
  selector: 'fm-story-tiles',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @for (story of stories(); track story.title; let s = $index) {
      <figure (mouseenter)="hovered.set(s)" (mouseleave)="hovered.set(-1)">
        @if (playing() === story.video && story.video) {
          <video
            [src]="story.video"
            [poster]="story.slides[0].image"
            controls
            autoplay
            playsinline
            (ended)="playing.set(null)"
          ></video>
        } @else {
          <div class="frames">
            @for (slide of story.slides; track slide.image; let i = $index) {
              <img
                [src]="slide.image"
                [alt]="i === slideFor(s, story) ? story.title + ' — ' + slide.place : ''"
                [class.on]="i === slideFor(s, story)"
                loading="lazy"
                decoding="async"
                width="900"
                height="675"
              />
            }
            <span class="place">{{ story.slides[slideFor(s, story)].place }}</span>
            @if (story.slides.length > 1) {
              <span class="dots" aria-hidden="true">
                @for (slide of story.slides; track slide.image; let i = $index) {
                  <i [class.on]="i === slideFor(s, story)"></i>
                }
              </span>
            }
          </div>
          @if (story.video) {
            <button type="button" class="play" (click)="playing.set(story.video!)">
              <ion-icon name="play-outline" aria-hidden="true" />
              Play with sound
            </button>
          }
        }
        <figcaption>
          <span class="tag">{{ story.tag }}</span>
          <strong>{{ story.title }}</strong>
          <span>{{ story.body }}</span>
        </figcaption>
      </figure>
    }
  `,
  styles: `
    :host {
      display: grid;
      align-items: start;
      gap: 12px;
      margin-top: 12px;
    }
    figure {
      position: relative;
      display: grid;
      align-content: start;
      margin: 0;
      overflow: hidden;
      border-radius: 18px;
      background: var(--fm-surface, #fff);
      box-shadow: 0 8px 24px rgb(15 23 42 / 8%);
    }
    .frames {
      position: relative;
      aspect-ratio: 4 / 3;
      background: #0b1220;
    }
    .frames img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      opacity: 0;
      transition: opacity 1.1s ease;
    }
    .frames img.on {
      opacity: 1;
    }
    video {
      display: block;
      width: 100%;
      height: auto;
      aspect-ratio: 4 / 3;
      object-fit: cover;
      background: #0b1220;
    }
    .place {
      position: absolute;
      left: 12px;
      bottom: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgb(15 23 42 / 62%);
      color: #fff;
      font-size: 0.74rem;
      font-weight: 700;
      backdrop-filter: blur(6px);
    }
    .dots {
      position: absolute;
      right: 12px;
      bottom: 16px;
      display: flex;
      gap: 5px;
    }
    .dots i {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: rgb(255 255 255 / 45%);
      transition: background 0.4s ease;
    }
    .dots i.on {
      background: #fff;
    }
    .play {
      position: absolute;
      top: 12px;
      right: 12px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 34px;
      padding: 0 12px;
      border: 1px solid rgb(255 255 255 / 40%);
      border-radius: 999px;
      background: rgb(15 23 42 / 60%);
      color: #fff;
      font: inherit;
      font-size: 0.8rem;
      font-weight: 700;
      backdrop-filter: blur(6px);
      cursor: pointer;
    }
    figcaption {
      display: grid;
      gap: 4px;
      padding: 14px 16px 16px;
    }
    figcaption span:last-child {
      color: var(--ion-color-medium);
      font-size: 0.86rem;
      line-height: 1.45;
    }
    .tag {
      justify-self: start;
      padding: 3px 8px;
      border-radius: 999px;
      background: color-mix(in srgb, #0f766e 16%, transparent);
      color: var(--fm-accent, #0f766e);
      font-size: 0.66rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    @media (min-width: 880px) {
      :host {
        grid-template-columns: 1fr 1fr;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .frames img {
        transition: none;
      }
    }
  `,
})
export class StoryTilesComponent {
  private readonly destroyRef = inject(DestroyRef);

  readonly stories = input.required<Story[]>();
  readonly playing = signal<string | null>(null);
  readonly hovered = signal(-1);
  /** One shared clock; each card's position is staggered so they do not change in step. */
  private readonly ticks = signal(0);

  constructor() {
    afterNextRender(() => {
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
      const timer = setInterval(() => {
        if (!document.hidden) this.ticks.update((value) => value + 1);
      }, FADE_EVERY_MS);
      this.destroyRef.onDestroy(() => clearInterval(timer));
    });
  }

  slideFor(index: number, story: Story): number {
    const count = story.slides.length;
    if (count < 2) return 0;
    const held = this.frozen[index];
    if (this.hovered() === index && held !== undefined) return held;
    const position = (this.ticks() + index) % count;
    this.frozen[index] = position;
    return position;
  }

  private readonly frozen: Record<number, number> = {};
}

interface Moment {
  image: string;
  tag: string;
  title: string;
  body: string;
}

/** Photo strip: the social side of match day. */
@Component({
  selector: 'fm-landing-moments',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p class="eyebrow">Match day, shared</p>
    <h2>Every result is a moment worth sharing</h2>
    <p class="lede">
      Score from the touchline, post the full-time photo, rate the players and argue about it in
      the feed — with your team, your office or the whole town.
    </p>
    <div class="grid">
      @for (moment of moments; track moment.image; let first = $first) {
        <figure [class.wide]="first">
          <img
            [src]="moment.image"
            [alt]="moment.title"
            loading="lazy"
            decoding="async"
            width="900"
            height="675"
          />
          <figcaption>
            <span class="tag">{{ moment.tag }}</span>
            <strong>{{ moment.title }}</strong>
            <span>{{ moment.body }}</span>
          </figcaption>
        </figure>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      margin-top: 36px;
    }
    .eyebrow {
      margin: 0 0 6px;
      color: #0f766e;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h2 {
      margin: 0;
    }
    .lede {
      max-width: 60ch;
      color: var(--ion-color-medium);
      line-height: 1.55;
    }
    .grid {
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }
    figure {
      position: relative;
      margin: 0;
      overflow: hidden;
      aspect-ratio: 4 / 3;
      border-radius: 18px;
      background: #0b1220;
      box-shadow: 0 8px 24px rgb(15 23 42 / 10%);
    }
    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.6s ease;
    }
    figure:hover img {
      transform: scale(1.04);
    }
    figcaption {
      position: absolute;
      inset: auto 0 0;
      display: grid;
      gap: 3px;
      padding: 40px 14px 14px;
      background: linear-gradient(0deg, rgb(4 10 22 / 88%), transparent);
      color: #fff;
    }
    figcaption span:last-child {
      color: rgb(255 255 255 / 80%);
      font-size: 0.82rem;
      line-height: 1.4;
    }
    .tag {
      justify-self: start;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgb(15 118 110 / 90%);
      font-size: 0.66rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    @media (min-width: 720px) {
      .grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      figure.wide {
        grid-column: 1 / -1;
        aspect-ratio: 16 / 9;
      }
    }
    @media (min-width: 1100px) {
      .grid {
        grid-template-columns: 2fr 1fr 1fr;
        grid-template-rows: repeat(2, minmax(0, 1fr));
      }
      figure.wide {
        grid-column: auto;
        grid-row: span 2;
        aspect-ratio: auto;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      img {
        transition: none;
      }
    }
  `,
})
export class LandingMomentsComponent {
  readonly moments: Moment[] = [
    {
      image: `${MEDIA}/moment-fans.jpg`,
      tag: 'The feed',
      title: 'Follow it together',
      body: 'Live scores, tables and reactions land in one feed your friends already check.',
    },
    {
      image: `${MEDIA}/moment-touchline.jpg`,
      tag: 'Live scoring',
      title: 'Score from the touchline',
      body: 'Tap a player for a goal or a card. The table updates for everyone.',
    },
    {
      image: `${MEDIA}/moment-office.jpg`,
      tag: 'Workplace',
      title: 'Office five-a-side',
      body: 'Run the after-work league with fixtures, ratings and bragging rights.',
    },
    {
      image: `${MEDIA}/moment-rugby.jpg`,
      tag: 'Clubs',
      title: 'Celebrate the result',
      body: 'Post the full-time photo and let the club rate the performance.',
    },
    {
      image: `${MEDIA}/gov-cleanup.jpg`,
      tag: 'Community',
      title: 'More than sport',
      body: 'Clean-ups, reading races and school challenges, scored your way.',
    },
  ];
}
