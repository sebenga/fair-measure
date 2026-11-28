import {
  AD_BREAK_SECONDS,
  AdBreakGate,
  HOUSE_COMPETITION_AD,
  adDurationSeconds,
  competitionAdCreative,
  formatAdCountdown,
} from './ad-break';

describe('competition ad creative', () => {
  it('plays the Fair Measure house ad for 30 seconds', () => {
    const creative = competitionAdCreative();
    expect(creative).toBe(HOUSE_COMPETITION_AD);
    expect(creative.durationSeconds).toBe(30);
    expect(creative.durationSeconds).toBe(AD_BREAK_SECONDS);
    expect(creative.id).toBe('fair-measure-house');
    expect(creative.href).toBe('https://fair-measure.com/');
  });

  it('falls back when a creative has no usable duration', () => {
    expect(adDurationSeconds({ ...HOUSE_COMPETITION_AD, durationSeconds: 0 })).toBe(30);
    expect(adDurationSeconds({ ...HOUSE_COMPETITION_AD, durationSeconds: 12.2 })).toBe(12);
  });

  it('formats the countdown clock', () => {
    expect(formatAdCountdown(30)).toBe('0:30');
    expect(formatAdCountdown(0)).toBe('0:00');
    expect(formatAdCountdown(75)).toBe('1:15');
    expect(formatAdCountdown(-4)).toBe('0:00');
  });
});

describe('AdBreakGate', () => {
  it('plays once for a public competition and ignores a refresh', () => {
    const gate = new AdBreakGate();
    gate.start();
    gate.enter();
    gate.consider(true);
    expect(gate.show).toBeTrue();

    gate.consider(true);
    expect(gate.show).toBeTrue();

    gate.complete();
    expect(gate.show).toBeFalse();
    gate.consider(true);
    expect(gate.show).toBeFalse();
  });

  it('does not play before the page is opened', () => {
    const gate = new AdBreakGate();
    gate.consider(true);
    expect(gate.show).toBeFalse();
  });

  it('skips private competitions', () => {
    const gate = new AdBreakGate();
    gate.start();
    gate.enter();
    gate.consider(false);
    expect(gate.show).toBeFalse();
    gate.consider(false);
    expect(gate.show).toBeFalse();
  });

  it('does not restart when the first Ionic enter arrives after the break has started', () => {
    const gate = new AdBreakGate();
    gate.start();
    gate.consider(true);
    gate.enter();
    gate.consider(true);
    expect(gate.show).toBeTrue();
    gate.complete();
    gate.consider(true);
    expect(gate.show).toBeFalse();
  });

  it('plays again the next time the page is opened', () => {
    const gate = new AdBreakGate();
    gate.start();
    gate.enter();
    gate.consider(true);
    const first = gate.opening;
    gate.complete();
    gate.leave();
    gate.enter();
    gate.consider(true);
    expect(gate.show).toBeTrue();
    expect(gate.opening).not.toBe(first);
  });

  it('stops when the visitor leaves mid-break and plays again on return', () => {
    const gate = new AdBreakGate();
    gate.start();
    gate.enter();
    gate.consider(true);
    gate.leave();
    expect(gate.show).toBeFalse();
    gate.enter();
    gate.consider(true);
    expect(gate.show).toBeTrue();
  });
});
