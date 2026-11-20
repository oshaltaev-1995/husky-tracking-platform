import { DOCUMENT } from '@angular/common';
import { afterNextRender, AfterRenderRef, ApplicationRef, ComponentRef, createComponent, EnvironmentInjector, inject, Injectable, OnDestroy, signal } from '@angular/core';

import { DogSummaryProjection } from './dog-summary-projection';
import { DogSummaryPreviewComponent, dogSummaryTitle } from './dog-summary-preview.component';

/** Page-provided lifecycle owner. There is no API request or mutation in this service. */
@Injectable()
export class DogSummaryPrintService implements OnDestroy {
  readonly isOpen = signal(false);
  private readonly document = inject(DOCUMENT);
  private readonly application = inject(ApplicationRef);
  private readonly environment = inject(EnvironmentInjector);
  private component: ComponentRef<DogSummaryPreviewComponent> | null = null;
  private host: HTMLElement | null = null;
  private trigger: HTMLElement | null = null;
  private previousTitle = '';
  private printTitle = '';
  private generation = 0;
  private destroyed = false;
  private pendingRestore: AfterRenderRef | null = null;

  open(projection: DogSummaryProjection): void {
    if (this.destroyed) return;
    this.close(false);
    if (this.document.querySelector('[role="dialog"][aria-modal="true"]')) return;
    this.generation++;
    this.trigger = this.document.activeElement as HTMLElement | null;
    this.previousTitle = this.document.title;
    this.printTitle = dogSummaryTitle(projection.name, projection.snapshotDate);
    const host = this.document.createElement('ht-dog-summary-preview');
    this.host = host;
    this.document.body.append(host);
    this.document.body.classList.add('ht-dog-summary-open');
    const component = createComponent(DogSummaryPreviewComponent, {
      environmentInjector: this.environment,
      hostElement: host,
    });
    this.component = component;
    component.setInput('projection', projection);
    component.instance.closed.subscribe(() => this.close(true));
    this.application.attachView(component.hostView);
    component.changeDetectorRef.detectChanges();
    this.isOpen.set(true);
  }

  close(restoreFocus = false): void {
    this.pendingRestore?.destroy();
    this.pendingRestore = null;
    const host = this.host;
    const trigger = this.trigger;
    const ownsFocus = !!host && (host.contains(this.document.activeElement) || this.document.activeElement === this.document.body);
    const component = this.component;
    this.component = null;
    this.host = null;
    this.trigger = null;
    const generation = ++this.generation;
    if (component) {
      this.application.detachView(component.hostView);
      component.destroy();
    }
    host?.remove();
    if (host) {
      this.document.body.classList.remove('ht-dog-summary-open');
      if (this.document.title === this.printTitle) this.document.title = this.previousTitle;
    }
    this.isOpen.set(false);
    if (restoreFocus && ownsFocus) {
      // The page may disable its Print summary trigger while isOpen is true. Wait for
      // that binding to render the closed state before checking/returning focus.
      this.pendingRestore = afterNextRender(() => {
        this.pendingRestore = null;
        const current = this.document.activeElement;
        const outsideFocus = current !== this.document.body && current?.isConnected;
        if (!this.destroyed && generation === this.generation && !outsideFocus &&
          !this.document.querySelector('[role="dialog"][aria-modal="true"]') &&
          trigger?.isConnected && !trigger.matches(':disabled') && !trigger.closest('[hidden], [inert]')) {
          trigger.focus({ preventScroll: true });
        }
      }, { injector: this.environment });
    }
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.close(false);
  }
}
