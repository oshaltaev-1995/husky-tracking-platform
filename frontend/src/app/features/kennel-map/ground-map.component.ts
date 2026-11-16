import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';

import { KennelMapLayer, KennelMapLocation } from '../../core/api/kennel-map.models';
import { KennelLocationCardComponent } from './kennel-location-card.component';
import { KennelBlockView } from './kennel-map-layout';

const MIN_SCALE = 0.25;
const MAX_SCALE = 1.75;
const ZOOM_FACTOR = 1.25;
const PAN_STEP = 48;

interface PointerPan {
  id: number;
  x: number;
  y: number;
  left: number;
  top: number;
}

@Component({
  selector: 'ht-ground-map',
  imports: [KennelLocationCardComponent],
  templateUrl: './ground-map.component.html',
  styleUrl: './ground-map.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GroundMapComponent {
  readonly blocks = input.required<KennelBlockView[]>();
  readonly puppyAreas = input.required<KennelMapLocation[]>();
  readonly layer = input.required<KennelMapLayer>();
  readonly highlightedDogId = input<string | null>(null);

  private readonly viewport = viewChild.required<ElementRef<HTMLDivElement>>('viewport');
  private readonly board = viewChild.required<ElementRef<HTMLDivElement>>('board');
  private readonly destroyRef = inject(DestroyRef);
  private followingFit = true;
  private drag: PointerPan | null = null;

  protected readonly scale = signal(1);
  protected readonly canZoomIn = computed(() => this.scale() < MAX_SCALE);
  protected readonly canZoomOut = computed(() => this.scale() > MIN_SCALE);
  protected readonly panning = signal(false);

  constructor() {
    afterNextRender(() => {
      const viewport = this.viewport().nativeElement;
      const board = this.board().nativeElement;
      this.fit();
      const highlighted = this.highlightedDogId();
      if (highlighted) this.revealDog(highlighted, false);

      const renderWindow = viewport.ownerDocument.defaultView;
      if (renderWindow && typeof ResizeObserver !== 'undefined') {
        let frame: number | null = null;
        const observer = new ResizeObserver(() => {
          if (this.destroyRef.destroyed || !this.followingFit || frame !== null) return;
          // Applying zoom writes layout. Defer it outside the resize delivery cycle.
          frame = renderWindow.requestAnimationFrame(() => {
            frame = null;
            if (!this.destroyRef.destroyed && this.followingFit) this.fitBoard();
          });
        });
        observer.observe(viewport);
        observer.observe(board);
        this.destroyRef.onDestroy(() => {
          observer.disconnect();
          if (frame !== null) renderWindow.cancelAnimationFrame(frame);
        });
      }
      this.destroyRef.onDestroy(() => this.endPan(viewport));
    });
  }

  protected fit(): void {
    this.followingFit = true;
    this.fitBoard();
    const viewport = this.viewport().nativeElement;
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  }

  private fitBoard(): void {
    const viewport = this.viewport().nativeElement;
    const board = this.board().nativeElement;
    if (!viewport.clientWidth || !viewport.clientHeight || !board.offsetWidth || !board.offsetHeight) {
      return;
    }
    // offset dimensions are unscaled. Leave a pixel for CSSOM rounding at fractional zoom.
    const fit = Math.min(
      1,
      (viewport.clientWidth - 1) / board.offsetWidth,
      (viewport.clientHeight - 1) / board.offsetHeight,
    );
    this.applyScale(Math.max(MIN_SCALE, fit));
  }

  protected zoomBy(direction: -1 | 1): void {
    const viewport = this.viewport().nativeElement;
    const board = this.board().nativeElement;
    const previous = this.scale();
    const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, previous * ZOOM_FACTOR ** direction));
    if (next === previous) return;
    this.followingFit = false;

    const viewportRect = viewport.getBoundingClientRect();
    const previousRect = board.getBoundingClientRect();
    const centerX = viewportRect.left + viewport.clientLeft + viewport.clientWidth / 2;
    const centerY = viewportRect.top + viewport.clientTop + viewport.clientHeight / 2;
    const xOnBoard = (centerX - previousRect.left) / previous;
    const yOnBoard = (centerY - previousRect.top) / previous;

    this.applyScale(next);
    const rect = board.getBoundingClientRect();
    viewport.scrollLeft += rect.left + xOnBoard * next - centerX;
    viewport.scrollTop += rect.top + yOnBoard * next - centerY;
  }

  private applyScale(scale: number): void {
    if (scale === this.scale()) return;
    // Zoom affects layout and scroll bounds; apply it before re-anchoring the viewport.
    this.board().nativeElement.style.zoom = String(scale);
    this.scale.set(scale);
  }

  revealDog(id: string, focus = true): void {
    const viewport = this.viewport().nativeElement;
    const link = viewport.ownerDocument.getElementById(`map-dog-${id}`);
    if (!link || !viewport.contains(link)) return;

    const view = viewport.getBoundingClientRect();
    const dog = link.getBoundingClientRect();
    viewport.scrollLeft += (dog.left + dog.right) / 2 - (view.left + viewport.clientLeft + viewport.clientWidth / 2);
    viewport.scrollTop += (dog.top + dog.bottom) / 2 - (view.top + viewport.clientTop + viewport.clientHeight / 2);
    if (focus) {
      viewport.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
      link.focus({ preventScroll: true });
    }
  }

  protected onPointerDown(event: PointerEvent): void {
    if (event.pointerType === 'touch' || event.button !== 0 || this.drag) return;
    if (event.target instanceof Element && event.target.closest('a, button, input, select, textarea, label, [contenteditable]')) {
      return;
    }
    const viewport = this.viewport().nativeElement;
    if (event.target === viewport) {
      const rect = viewport.getBoundingClientRect();
      // Leave the native scrollbar available for direct interaction.
      if (event.clientX >= rect.left + viewport.clientLeft + viewport.clientWidth ||
          event.clientY >= rect.top + viewport.clientTop + viewport.clientHeight) return;
    }
    this.drag = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      left: viewport.scrollLeft,
      top: viewport.scrollTop,
    };
    viewport.setPointerCapture?.(event.pointerId);
  }

  protected onPointerMove(event: PointerEvent): void {
    const drag = this.drag;
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!this.panning() && Math.hypot(dx, dy) < 5) return;
    this.panning.set(true);
    event.preventDefault();
    const viewport = this.viewport().nativeElement;
    viewport.scrollLeft = drag.left - dx;
    viewport.scrollTop = drag.top - dy;
  }

  protected onPointerEnd(event: PointerEvent): void {
    if (event.pointerId === this.drag?.id) this.endPan(this.viewport().nativeElement);
  }

  private endPan(viewport: HTMLDivElement): void {
    const drag = this.drag;
    this.drag = null;
    if (!drag) return;
    this.panning.set(false);
    if (viewport.hasPointerCapture?.(drag.id)) viewport.releasePointerCapture(drag.id);
  }

  protected onKeyDown(event: KeyboardEvent): void {
    const viewport = this.viewport().nativeElement;
    if (
      event.target !== viewport ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.defaultPrevented
    ) return;
    switch (event.key) {
      case 'ArrowLeft': viewport.scrollLeft -= PAN_STEP; break;
      case 'ArrowRight': viewport.scrollLeft += PAN_STEP; break;
      case 'ArrowUp': viewport.scrollTop -= PAN_STEP; break;
      case 'ArrowDown': viewport.scrollTop += PAN_STEP; break;
      case '+':
      case '=': this.zoomBy(1); break;
      case '-': this.zoomBy(-1); break;
      case '0': this.fit(); break;
      default: return;
    }
    event.preventDefault();
  }
}
