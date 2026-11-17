import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { GroundMapComponent } from './ground-map.component';

describe('Ground map viewport', () => {
  let fixture: ComponentFixture<GroundMapComponent>;
  let viewport: HTMLElement;
  let board: HTMLElement;
  let viewportWidth: number;
  let boardHeight: number;
  let onResize: () => void;
  let deliveringResize = false;
  let resizeFrame: FrameRequestCallback;
  const resizeFrameId = 700_000;
  const observe = vi.fn();
  const disconnect = vi.fn();
  const requestFrame = vi.fn((callback: FrameRequestCallback) => {
    resizeFrame = callback;
    return resizeFrameId;
  });
  const cancelFrame = vi.fn();

  function resize(): void {
    deliveringResize = true;
    try {
      onResize();
    } finally {
      deliveringResize = false;
    }
  }

  function zoom(): number {
    return Number(board.style.getPropertyValue('zoom') || '1');
  }

  function button(label: string): HTMLButtonElement {
    return fixture.nativeElement.querySelector(`button[aria-label="${label}"]`);
  }

  function fit(): void {
    (fixture.nativeElement.querySelector('.zoom-controls button:last-child') as HTMLElement).click();
  }

  function pointer(element: HTMLElement, type: string, x: number, y: number, pointerType = 'mouse') {
    const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y });
    Object.defineProperties(event, {
      pointerId: { value: 1 },
      pointerType: { value: pointerType },
    });
    element.dispatchEvent(event);
  }

  beforeEach(async () => {
    observe.mockClear();
    disconnect.mockClear();
    requestFrame.mockClear();
    cancelFrame.mockClear();
    const nativeRequest = window.requestAnimationFrame.bind(window);
    const nativeCancel = window.cancelAnimationFrame.bind(window);
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) =>
      deliveringResize ? requestFrame(callback) : nativeRequest(callback),
    );
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      if (id === resizeFrameId) cancelFrame(id);
      else nativeCancel(id);
    });
    vi.stubGlobal('ResizeObserver', class {
      observe = observe;
      disconnect = disconnect;
      constructor(callback: () => void) {
        onResize = callback;
      }
    });
    fixture = TestBed.createComponent(GroundMapComponent);
    fixture.componentRef.setInput('blocks', []);
    fixture.componentRef.setInput('puppyAreas', []);
    fixture.componentRef.setInput('layer', 'default');
    fixture.detectChanges();
    await fixture.whenStable();

    viewport = fixture.nativeElement.querySelector('.ground-viewport');
    board = fixture.nativeElement.querySelector('.ground-board');
    viewportWidth = 501;
    boardHeight = 600;
    Object.defineProperties(viewport, {
      clientWidth: { get: () => viewportWidth },
      clientHeight: { value: 401 },
    });
    Object.defineProperties(board, {
      offsetWidth: { value: 1000 },
      offsetHeight: { get: () => boardHeight },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('fits both axes and recomputes after viewport and content resizes; disconnects on destroy', () => {
    expect(observe.mock.calls.map(([element]) => element)).toEqual([viewport, board]);
    fit();
    expect(zoom()).toBeCloseTo(0.5);
    viewportWidth = 801;
    resize();
    resize();
    expect(requestFrame).toHaveBeenCalledTimes(1);
    expect(zoom()).toBeCloseTo(0.5);
    resizeFrame(0);
    expect(zoom()).toBeCloseTo(400 / 600);
    boardHeight = 1000;
    resize();
    resizeFrame(0);
    expect(zoom()).toBeCloseTo(0.4);
    resize();
    fixture.destroy();
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(cancelFrame).toHaveBeenCalledWith(resizeFrameId);
  });

  it('keeps Fit and manual zoom within limits and preserves manual zoom on resize', () => {
    viewportWidth = 1;
    resize();
    resizeFrame(0);
    fixture.detectChanges();
    expect(zoom()).toBe(0.25);
    expect(button('Zoom out').disabled).toBe(true);

    for (let step = 0; step < 12; step++) button('Zoom in').click();
    fixture.detectChanges();
    expect(zoom()).toBe(1.75);
    expect(button('Zoom in').disabled).toBe(true);
    viewportWidth = 901;
    resize();
    expect(zoom()).toBe(1.75);
    fit();
    expect(zoom()).toBeCloseTo(400 / 600);
  });

  it('pans with keyboard and pointer without intercepting links or touch', () => {
    viewport.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(viewport.scrollLeft).toBe(48);
    pointer(board, 'pointerdown', 180, 150);
    pointer(board, 'pointermove', 80, 110);
    pointer(board, 'pointerup', 80, 110);
    expect(viewport.scrollLeft).toBe(148);
    expect(viewport.scrollTop).toBe(40);

    const link = document.createElement('a');
    link.href = '/demo/dogs/test';
    board.append(link);
    pointer(link, 'pointerdown', 180, 150);
    pointer(link, 'pointermove', 80, 110);
    pointer(link, 'pointerup', 80, 110);
    pointer(board, 'pointerdown', 180, 150, 'touch');
    pointer(board, 'pointermove', 80, 110, 'touch');
    expect(viewport.scrollLeft).toBe(148);
    expect(viewport.scrollTop).toBe(40);
  });

  it('centers the found link inside the map before revealing and focusing it in the browser', () => {
    const link = document.createElement('a');
    link.id = 'map-dog-puppy-last';
    link.href = '/demo/dogs/puppy-last';
    board.append(link);
    Object.defineProperties(viewport, {
      clientLeft: { value: 2 },
      clientTop: { value: 3 },
    });
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(new DOMRect(10, 100, 505, 405));
    vi.spyOn(link, 'getBoundingClientRect').mockReturnValue(new DOMRect(700, 650, 100, 30));
    const order: string[] = [];
    let behavior: ScrollBehavior | undefined;
    link.scrollIntoView = vi.fn((options?: boolean | ScrollIntoViewOptions) => {
      if (typeof options === 'object') behavior = options.behavior;
      expect(viewport.scrollLeft).toBeCloseTo(487.5);
      expect(viewport.scrollTop).toBeCloseTo(361.5);
      order.push('reveal link');
    });
    const originalFocus = link.focus.bind(link);
    const focus = vi.spyOn(link, 'focus').mockImplementation((options) => {
      order.push('focus link');
      originalFocus(options);
    });

    fixture.componentInstance.revealDog('puppy-last');
    expect(order).toEqual(['reveal link', 'focus link']);
    expect(behavior).toBe('instant');
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(document.activeElement).toBe(link);
  });

  it('silently preserves a found position when switching views and ignores links outside its viewport', () => {
    const link = document.createElement('a');
    link.id = 'map-dog-highlighted';
    link.href = '/demo/dogs/highlighted';
    board.append(link);
    link.scrollIntoView = vi.fn();
    const focus = vi.spyOn(link, 'focus');
    fixture.componentInstance.revealDog('highlighted', false);
    expect(link.scrollIntoView).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();

    fixture.nativeElement.append(link);
    fixture.componentInstance.revealDog('highlighted');
    expect(link.scrollIntoView).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
  });
});
