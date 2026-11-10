import { Injectable, signal } from '@angular/core';

const VOICE_KEY = 'fm.guide.voice';
/** Preferred English accents, best first. */
const ACCENTS = ['en-za', 'en-gb', 'en-us', 'en-au', 'en'];
/** macOS ships joke voices that are no good for a tour. */
const NOVELTY =
  /^(albert|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|fred|junior|ralph|kathy|grandma|grandpa|eddy|flo|reed|rocko|sandy|shelley)\b/i;

/** Coach Kaya's spoken English narration, using the browser's own speech synthesis. */
@Injectable({ providedIn: 'root' })
export class DemoVoiceService {
  readonly supported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  readonly on = signal(this.supported && localStorage.getItem(VOICE_KEY) !== 'off');
  readonly speaking = signal(false);

  private voice: SpeechSynthesisVoice | null = null;
  private turn = 0;
  /** Said before the page was touched; browsers only allow speech after a tap. */
  private waiting: string | null = null;
  private listening = false;
  /** Set by the first tap or key press anywhere; some browsers misreport this themselves. */
  private tapped = false;

  constructor() {
    if (!this.supported) return;
    const tap = () => {
      this.tapped = true;
      document.removeEventListener('pointerdown', tap, true);
      document.removeEventListener('keydown', tap, true);
    };
    document.addEventListener('pointerdown', tap, true);
    document.addEventListener('keydown', tap, true);
    this.pickVoice();
    speechSynthesis.addEventListener('voiceschanged', () => this.pickVoice());
  }

  toggle(): void {
    if (!this.supported) return;
    const next = !this.on();
    this.on.set(next);
    localStorage.setItem(VOICE_KEY, next ? 'on' : 'off');
    if (!next) this.hush();
  }

  /** Speaks the text and resolves when it has been said, cut off or skipped. */
  say(text: string): Promise<void> {
    if (!this.supported || !this.on() || !text.trim()) return Promise.resolve();
    if (!this.tapped && !browserSaysTouched()) {
      this.sayOnFirstTap(text);
      return Promise.resolve();
    }
    this.hush();
    const turn = this.turn;
    // Chrome stops long utterances after about 15 seconds, so speak sentence by sentence.
    const sentences = text.match(/[^.!?…]+[.!?…]*/g)?.map((part) => part.trim()).filter(Boolean) ?? [text];
    this.speaking.set(true);
    return new Promise<void>((resolve) => {
      let left = sentences.length;
      const done = () => {
        if (turn === this.turn) this.speaking.set(false);
        resolve();
      };
      // Some browsers never fire `end` when speech is blocked; don't hold the tour up.
      const guard = setTimeout(done, 4000 + text.length * 90);
      for (const sentence of sentences) {
        const utterance = new SpeechSynthesisUtterance(sentence);
        if (this.voice) utterance.voice = this.voice;
        utterance.lang = this.voice?.lang ?? 'en-GB';
        utterance.rate = 1;
        utterance.pitch = 1.05;
        const finish = () => {
          left--;
          if (left > 0 && turn === this.turn) return;
          clearTimeout(guard);
          done();
        };
        utterance.onend = finish;
        utterance.onerror = (event) => {
          // iOS refuses speech until the first tap even when the page reports no tap yet.
          if (event.error === 'not-allowed') this.sayOnFirstTap(text);
          finish();
        };
        speechSynthesis.speak(utterance);
      }
    });
  }

  hush(): void {
    if (!this.supported) return;
    this.waiting = null;
    this.turn++;
    this.speaking.set(false);
    speechSynthesis.cancel();
  }

  /** Holds the latest line and says it on the first tap or key press, within that gesture. */
  private sayOnFirstTap(text: string): void {
    this.waiting = text;
    if (this.listening) return;
    this.listening = true;
    const speak = () => {
      document.removeEventListener('pointerdown', speak, true);
      document.removeEventListener('keydown', speak, true);
      this.listening = false;
      const line = this.waiting;
      this.waiting = null;
      if (line && this.on()) void this.say(line);
    };
    document.addEventListener('pointerdown', speak, true);
    document.addEventListener('keydown', speak, true);
  }

  private pickVoice(): void {
    const english = speechSynthesis
      .getVoices()
      .filter((voice) => voice.lang.toLowerCase().startsWith('en') && !NOVELTY.test(voice.name));
    for (const accent of ACCENTS) {
      const matches = english.filter((voice) => voice.lang.toLowerCase().replace('_', '-').startsWith(accent));
      const best = matches.find((voice) => /natural|google|samantha|daniel|serena|karen/i.test(voice.name)) ?? matches[0];
      if (best) {
        this.voice = best;
        return;
      }
    }
    this.voice = null;
  }
}

/** The browser's own record of a tap or key press; unknown counts as yes. */
function browserSaysTouched(): boolean {
  const activation = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } })
    .userActivation;
  return activation ? activation.hasBeenActive : true;
}
