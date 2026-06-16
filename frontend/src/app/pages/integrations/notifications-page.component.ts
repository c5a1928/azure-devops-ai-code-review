import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import {
  ReviewSettings,
  ReviewSettingsInput,
  SECRET_PLACEHOLDER,
  toSettingsForm,
} from '../../models/types';

@Component({
  selector: 'app-notifications-page',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="page-header">
      <h1>Notifications</h1>
      <p>Send an email summary when a review completes. Gmail app passwords are supported.</p>
    </div>

    @if (loading) {
      <div class="card">Loading...</div>
    } @else {
      <form class="card" (ngSubmit)="save()">
        @if (error) {
          <div class="alert error">{{ error }}</div>
        }
        @if (message) {
          <div class="alert success">{{ message }}</div>
        }

        <h2>Email</h2>
        <p class="subtitle">Optional. Leave blank to skip email notifications.</p>

        <div class="grid-2">
          <div class="field">
            <label for="gmailUser">Gmail address</label>
            <input id="gmailUser" type="email" [(ngModel)]="form.gmail_user" name="gmailUser" />
          </div>
          <div class="field">
            <label for="gmailPassword">Gmail app password</label>
            <input
              id="gmailPassword"
              type="password"
              [(ngModel)]="passwordInput"
              name="gmailPassword"
              [placeholder]="status?.gmail_app_password_masked || 'Optional'"
            />
            @if (status?.gmail_app_password_configured) {
              <small>Configured: {{ status?.gmail_app_password_masked }}</small>
            }
          </div>
        </div>

        <div class="actions">
          <button class="primary" type="submit" [disabled]="saving">
            {{ saving ? 'Saving...' : 'Save notification settings' }}
          </button>
        </div>
      </form>
    }
  `,
})
export class NotificationsPageComponent implements OnInit {
  form!: ReviewSettingsInput;
  status: ReviewSettings | null = null;
  passwordInput = '';
  loading = true;
  saving = false;
  error = '';
  message = '';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
  ) {}

  async ngOnInit(): Promise<void> {
    try {
      const settings = await this.api.getSettings();
      this.status = settings;
      this.form = toSettingsForm(settings);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load settings';
    } finally {
      this.loading = false;
    }
  }

  async save(): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    this.saving = true;
    this.error = '';
    this.message = '';
    try {
      const current = await this.api.getSettings();
      const payload: ReviewSettingsInput = {
        ...toSettingsForm(current),
        gmail_user: this.form.gmail_user,
        gmail_app_password:
          this.passwordInput ||
          (this.status?.gmail_app_password_configured ? SECRET_PLACEHOLDER : ''),
        git_token: current.git_token_configured ? SECRET_PLACEHOLDER : '',
        openai_api_key: current.openai_api_key_configured ? SECRET_PLACEHOLDER : '',
      };
      this.status = await this.api.saveSettings(payload);
      this.form = toSettingsForm(this.status);
      this.passwordInput = '';
      this.message = 'Notification settings saved.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      this.saving = false;
    }
  }
}
