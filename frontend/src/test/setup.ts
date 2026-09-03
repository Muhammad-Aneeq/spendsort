/**
 * Test environment setup.
 *
 * These tests substitute for visual inspection, which is unavailable in this environment
 * (BLOCKERS.md B7). They cannot judge layout — no assertion here knows whether a label
 * collides with an axis. What they do catch is the failure that actually breaks a demo: a
 * screen that throws on mount, or a chart handed a shape it cannot render.
 */

import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Recharts measures its container; jsdom reports every element as 0x0, so charts would render
// nothing and their internals would never execute. Giving ResizeObserver and the box metrics
// real numbers is what makes the chart code genuinely exercised rather than skipped.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, value: 800 });
Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 400 });

HTMLElement.prototype.getBoundingClientRect = function getBoundingClientRect() {
  return {
    width: 800,
    height: 400,
    top: 0,
    left: 0,
    bottom: 400,
    right: 800,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect;
};
