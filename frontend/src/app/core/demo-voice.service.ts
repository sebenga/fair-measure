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

  constructor() {
    if (!this.supported) return;
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
        utterance.onerror = finish;
        speechSynthesis.speak(utterance);
      }
    });
  }

  hush(): void {
    if (!this.supported) return;
    this.turn++;
    this.speaking.set(false);
    speechSynthesis.cancel();
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
