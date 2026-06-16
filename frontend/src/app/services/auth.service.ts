import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import Keycloak from 'keycloak-js';
import { AuthStatus } from '../models/auth';

const TOKEN_KEY = 'plyrev_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private keycloak: Keycloak | null = null;
  private status: AuthStatus | null = null;
  private legacyToken: string | null = null;
  private initPromise: Promise<boolean> | null = null;

  constructor(
    private readonly http: HttpClient,
    private readonly router: Router,
  ) {}

  get provider(): AuthStatus['provider'] {
    return this.status?.provider ?? 'none';
  }

  isAuthRequired(): boolean {
    return Boolean(this.status?.auth_required);
  }

  isAuthenticated(): boolean {
    if (!this.isAuthRequired()) {
      return true;
    }
    if (this.keycloak?.authenticated) {
      return true;
    }
    return Boolean(this.legacyToken);
  }

  getDisplayName(): string | null {
    if (!this.isAuthenticated()) {
      return null;
    }
    if (this.keycloak?.authenticated) {
      return (
        (this.keycloak.tokenParsed?.['preferred_username'] as string | undefined) ||
        (this.keycloak.tokenParsed?.['email'] as string | undefined) ||
        null
      );
    }
    return this.provider === 'password' ? 'Admin' : null;
  }

  async ensureInitialized(): Promise<boolean> {
    if (!this.initPromise) {
      this.initPromise = this.init();
    }
    return this.initPromise;
  }

  async init(): Promise<boolean> {
    this.status = await firstValueFrom(this.http.get<AuthStatus>('/api/auth/status'));
    if (!this.status.auth_required) {
      return true;
    }

    if (this.status.provider === 'keycloak' && this.status.keycloak) {
      return this.initKeycloak(this.status.keycloak);
    }

    this.legacyToken = localStorage.getItem(TOKEN_KEY);
    return Boolean(this.legacyToken);
  }

  getAccessToken(): string | null {
    if (this.keycloak?.authenticated && this.keycloak.token) {
      return this.keycloak.token;
    }
    return this.legacyToken;
  }

  requireAuthForAction(returnUrl: string): boolean {
    if (this.isAuthenticated()) {
      return true;
    }
    void this.router.navigate(['/login'], { queryParams: { returnUrl } });
    return false;
  }

  loginRedirectUri(returnUrl: string): string {
    const params = new URLSearchParams({ returnUrl });
    return `${window.location.origin}/login?${params.toString()}`;
  }

  async login(returnUrl = '/console/review'): Promise<void> {
    if (!this.keycloak) {
      throw new Error('Keycloak is not configured');
    }
    await this.keycloak.login({ redirectUri: this.loginRedirectUri(returnUrl) });
  }

  async register(returnUrl = '/console/review'): Promise<void> {
    if (!this.keycloak) {
      throw new Error('Keycloak is not configured');
    }
    await this.keycloak.register({ redirectUri: this.loginRedirectUri(returnUrl) });
  }

  async logout(): Promise<void> {
    if (this.keycloak) {
      await this.keycloak.logout({ redirectUri: window.location.origin });
      return;
    }
    this.legacyToken = null;
    localStorage.removeItem(TOKEN_KEY);
    void this.router.navigateByUrl('/');
  }

  setLegacyToken(token: string): void {
    this.legacyToken = token;
    localStorage.setItem(TOKEN_KEY, token);
  }

  private async initKeycloak(config: NonNullable<AuthStatus['keycloak']>): Promise<boolean> {
    this.keycloak = new Keycloak({
      url: config.url,
      realm: config.realm,
      clientId: config.client_id,
    });

    const authenticated = await this.keycloak.init({
      onLoad: 'check-sso',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    });

    if (authenticated) {
      this.scheduleTokenRefresh();
    }

    return authenticated;
  }

  private scheduleTokenRefresh(): void {
    if (!this.keycloak) {
      return;
    }
    this.keycloak.onTokenExpired = () => {
      void this.keycloak?.updateToken(30).catch(() => {
        void this.keycloak?.login();
      });
    };
  }
}
