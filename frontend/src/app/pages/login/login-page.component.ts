import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="login-shell">
      <div class="card login-card">
        <a routerLink="/" class="back-link">← Home</a>

        <div class="sidebar-brand" style="border: none; padding: 0 0 0.75rem; background: transparent;">
          <img src="favicon-32x32.png" alt="" class="brand-logo" width="22" height="22" />
          <div class="brand-text" style="color: var(--pr-text);">PlyRev</div>
        </div>
        <h2 style="margin: 0 0 0.25rem; font-weight: 700; font-size: 1rem; letter-spacing: -0.02em;">
          Sign in to run reviews
        </h2>
        <p class="subtitle">
          @if (provider === 'keycloak') {
            Create an account or sign in to queue AI-powered pull request reviews.
          } @else if (authRequired) {
            Enter the admin password configured in ADMIN_PASSWORD.
          } @else {
            Open the console to configure git platforms and run AI reviews.
          }
        </p>

        @if (error) {
          <div class="alert error">{{ error }}</div>
        }

        @if (provider === 'keycloak') {
          <div class="actions auth-actions">
            <button class="primary" type="button" [disabled]="loading" (click)="signIn()">
              {{ loading ? 'Redirecting...' : 'Sign in' }}
            </button>
            <button class="secondary" type="button" [disabled]="loading" (click)="signUp()">
              Sign up
            </button>
          </div>
        } @else if (authRequired) {
          <form (ngSubmit)="handleSubmit()">
            <div class="field">
              <label for="password">Admin password</label>
              <input
                id="password"
                type="password"
                [(ngModel)]="password"
                name="password"
                autocomplete="current-password"
                required
              />
            </div>
            <div class="actions">
              <button class="primary" type="submit" [disabled]="loading">
                {{ loading ? 'Signing in...' : 'Sign in' }}
              </button>
            </div>
          </form>
        } @else {
          <div class="actions">
            <button class="primary" type="button" (click)="continueWithoutPassword()">
              Open console
            </button>
          </div>
        }
      </div>
    </div>
  `,
})
export class LoginPageComponent implements OnInit {
  authRequired = false;
  provider: 'keycloak' | 'password' | 'none' = 'none';
  password = '';
  error = '';
  loading = false;
  private returnUrl = '/console/review';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
  ) {}

  async ngOnInit(): Promise<void> {
    this.returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/console/review';
    await this.auth.ensureInitialized();
    this.authRequired = this.auth.isAuthRequired();
    this.provider = this.auth.provider;

    if (this.auth.isAuthenticated()) {
      void this.router.navigateByUrl(this.returnUrl);
    }
  }

  async signIn(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      await this.auth.login(this.returnUrl);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Sign in failed';
      this.loading = false;
    }
  }

  async signUp(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      await this.auth.register(this.returnUrl);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Sign up failed';
      this.loading = false;
    }
  }

  async handleSubmit(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      const response = await this.api.login(this.password);
      this.auth.setLegacyToken(response.access_token);
      await this.router.navigateByUrl(this.returnUrl);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      this.loading = false;
    }
  }

  async continueWithoutPassword(): Promise<void> {
    this.error = '';
    try {
      const response = await this.api.login('');
      this.auth.setLegacyToken(response.access_token);
      await this.router.navigateByUrl(this.returnUrl);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Unable to start session';
    }
  }
}
