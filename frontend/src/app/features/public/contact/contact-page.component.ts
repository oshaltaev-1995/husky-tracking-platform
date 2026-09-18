import { ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ContactService } from '../../../core/api/contact.service';

type SubmissionState = 'idle' | 'sending' | 'success' | 'error';

@Component({
  selector: 'ht-contact-page',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './contact-page.component.html',
  styleUrl: './contact-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContactPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly contact = inject(ContactService);
  private readonly statusMessage = viewChild<ElementRef<HTMLElement>>('statusMessage');

  protected readonly state = signal<SubmissionState>('idle');
  protected readonly responseMessage = signal('');
  protected readonly form = this.formBuilder.nonNullable.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    company: ['', [Validators.maxLength(160)]],
    subject: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(160)]],
    message: ['', [Validators.required, Validators.minLength(20), Validators.maxLength(5000)]],
    website: [''],
  });

  protected submit(): void {
    if (this.form.invalid || this.state() === 'sending') {
      this.form.markAllAsTouched();
      const firstInvalid = document.querySelector<HTMLElement>('.contact-form .ng-invalid');
      firstInvalid?.focus();
      return;
    }

    this.state.set('sending');
    this.responseMessage.set('');
    this.contact.submit(this.form.getRawValue()).subscribe({
      next: (response) => {
        this.state.set('success');
        this.responseMessage.set(response.message);
        this.form.reset();
        this.focusStatus();
      },
      error: () => {
        this.state.set('error');
        this.responseMessage.set(
          'The message could not be delivered right now. Your text is still here—please try again later.',
        );
        this.focusStatus();
      },
    });
  }

  protected invalid(name: 'name' | 'email' | 'subject' | 'message'): boolean {
    const control = this.form.controls[name];
    return control.invalid && (control.touched || control.dirty);
  }

  private focusStatus(): void {
    setTimeout(() => this.statusMessage()?.nativeElement.focus(), 0);
  }
}
