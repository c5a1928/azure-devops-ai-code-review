import { Component } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';
import { AsyncPipe } from '@angular/common';
import { AuthService } from '../services/auth.service';

const PAGE_TITLES: Record<string, string> = {
  '/console/review': 'Run review',
  '/console/jobs': 'Jobs',
  '/console/projects': 'Projects',
  '/console/integrations/git': 'Git platform',
  '/console/integrations/ai': 'AI model',
  '/console/integrations/notifications': 'Notifications',
};

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, AsyncPipe],
  template: `
    <div class="console">
      <aside class="sidebar">
        <a routerLink="/" class="sidebar-brand">
          <img src="favicon-32x32.png" alt="" class="brand-logo" width="22" height="22" />
          <div class="brand-text">PlyRev</div>
        </a>

        <div class="sidebar-section">Project</div>
        <nav class="sidebar-nav">
          <a
            routerLink="/console/review"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: true }"
          >
            Run review
          </a>
          <a
            routerLink="/console/jobs"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: true }"
          >
            Jobs
          </a>
          <a
            routerLink="/console/projects"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: true }"
          >
            Projects
          </a>
        </nav>

        <div class="sidebar-section">Integrations</div>
        <nav class="sidebar-nav">
          <a routerLink="/console/integrations/git" routerLinkActive="active">Git platform</a>
          <a routerLink="/console/integrations/ai" routerLinkActive="active">AI model</a>
          <a routerLink="/console/integrations/notifications" routerLinkActive="active">
            Notifications
          </a>
        </nav>

        <div class="sidebar-footer">
          <a routerLink="/">Home</a>
        </div>
      </aside>

      <div class="main-area">
        <header class="topbar">
          <div class="topbar-title">{{ pageTitle$ | async }}</div>
          <div class="topbar-user">
            @if (displayName) {
              <span class="user-label">{{ displayName }}</span>
              <button type="button" class="link-button" (click)="logout()">Sign out</button>
            } @else {
              <a routerLink="/login" [queryParams]="{ returnUrl: currentUrl }" class="link-button">
                Sign in
              </a>
            }
          </div>
        </header>

        @if (!signedIn && showExploreBanner) {
          <div class="explore-banner">
            Exploring without sign-in.
            <a routerLink="/login" [queryParams]="{ returnUrl: currentUrl }">Sign in</a>
            to save settings and run reviews.
          </div>
        }

        <main class="content">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
})
export class LayoutComponent {
  pageTitle$;
  displayName: string | null;
  currentUrl = '/console/review';
  showExploreBanner = false;
  signedIn = false;

  constructor(
    private readonly router: Router,
    private readonly auth: AuthService,
  ) {
    this.signedIn = this.auth.isAuthenticated();
    this.displayName = this.auth.getDisplayName();
    this.updateRouteState(this.router.url);
    this.pageTitle$ = this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map((event) => {
        const url = (event as NavigationEnd).urlAfterRedirects;
        this.updateRouteState(url);
        return PAGE_TITLES[url] || 'PlyRev';
      }),
      startWith(PAGE_TITLES[this.router.url] || 'PlyRev'),
    );
  }

  logout(): void {
    void this.auth.logout();
  }

  private updateRouteState(url: string): void {
    this.currentUrl = url;
    this.signedIn = this.auth.isAuthenticated();
    this.displayName = this.auth.getDisplayName();
    this.showExploreBanner =
      url.includes('/integrations/') || url.includes('/console/projects');
  }
}
