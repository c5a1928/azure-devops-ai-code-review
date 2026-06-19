import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';

interface FeatureCard {
  icon: string;
  title: string;
  description: string;
  link: string;
}

@Component({
  selector: 'app-landing-page',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="landing">
      <header class="landing-header">
        <a routerLink="/" class="landing-brand">
          <img src="favicon-32x32.png" alt="" class="brand-logo" width="22" height="22" />
          <span class="brand-text">PlyRev</span>
        </a>
        <div class="landing-actions">
          @if (signedIn) {
            <a routerLink="/console/review" class="button-link primary">Open console</a>
          } @else {
            <a routerLink="/login" class="button-link subtle">Sign in</a>
            <a
              routerLink="/login"
              [queryParams]="{ returnUrl: '/console/review' }"
              class="button-link primary"
            >
              Run a review
            </a>
          }
        </div>
      </header>

      <div class="landing-main">
        <section class="hero">
          <div class="hero-copy">
            <p class="eyebrow">AI pull request reviews</p>
            <h1>Automated, context-aware feedback on every merge request</h1>
            <p class="hero-lead">
              Connect your git platform, pick an LLM, and get senior-engineer quality comments
              posted inline — with work-item context and framework-aware analysis.
            </p>
            <div class="hero-cta">
              <a
                routerLink="/login"
                [queryParams]="{ returnUrl: '/console/review' }"
                class="button-link primary large"
              >
                Run a review
              </a>
              <a routerLink="/console/integrations/git" class="button-link secondary large">
                Explore integrations
              </a>
            </div>
            <p class="hero-note">Browse settings without signing in. Sign in only to queue reviews.</p>
          </div>
          <div class="hero-panel card">
            <h3>Included in every review</h3>
            <ul class="hero-list">
              <li>Up to 8 anchored inline comments on changed lines</li>
              <li>Azure DevOps work-item and acceptance-criteria context</li>
              <li>Detects FastAPI, Django, SQLAlchemy, Celery, and more</li>
              <li>Optional email summary when a review completes</li>
            </ul>
          </div>
        </section>

        <section id="features" class="section">
          <div class="section-heading">
            <h2>Built for engineering teams</h2>
            <p>Configure git, AI, and notifications from the console.</p>
          </div>
          <div class="feature-grid">
            @for (feature of features; track feature.title) {
              <a [routerLink]="feature.link" class="feature-card card">
                <div class="feature-icon">{{ feature.icon }}</div>
                <h3>{{ feature.title }}</h3>
                <p>{{ feature.description }}</p>
                <span class="feature-link">Open →</span>
              </a>
            }
          </div>
        </section>
      </div>

      <section id="how-it-works" class="section section-muted">
        <div class="landing-main">
          <div class="section-heading">
            <h2>How it works</h2>
            <p>From connection to inline comments in three steps.</p>
          </div>
          <ol class="steps">
            <li class="step card">
              <span class="step-num">1</span>
              <div>
                <h3>Connect git</h3>
                <p>Azure DevOps, GitHub, GitLab, or Bitbucket — cloud or self-hosted.</p>
              </div>
            </li>
            <li class="step card">
              <span class="step-num">2</span>
              <div>
                <h3>Choose AI model</h3>
                <p>OpenAI, Anthropic, Gemini, Cursor, or any compatible API.</p>
              </div>
            </li>
            <li class="step card">
              <span class="step-num">3</span>
              <div>
                <h3>Run a review</h3>
                <p>Enter a PR ID and let the model post actionable inline feedback.</p>
              </div>
            </li>
          </ol>
        </div>
      </section>

      <div class="landing-main">
        <section class="section cta-section">
          <div class="cta-card card">
            <div class="cta-copy">
              <h2>Ready for your next pull request?</h2>
              <p>Sign in to queue a review, or browse integrations first.</p>
            </div>
            <div class="hero-cta">
              <a
                routerLink="/login"
                [queryParams]="{ returnUrl: '/console/review' }"
                class="button-link primary"
              >
                Sign in
              </a>
              <a routerLink="/console/integrations/git" class="button-link secondary">
                Integrations
              </a>
            </div>
          </div>
        </section>
      </div>

      <footer class="landing-footer">
        <span>PlyRev</span>
        <a routerLink="/console/integrations/git">Integrations</a>
        <a routerLink="/login" [queryParams]="{ returnUrl: '/console/review' }">Sign in</a>
      </footer>
    </div>
  `,
})
export class LandingPageComponent {
  readonly features: FeatureCard[] = [
    {
      icon: 'GIT',
      title: 'Multi-platform git',
      description: 'ADO, GitHub, GitLab, and Bitbucket with cloud and self-hosted presets.',
      link: '/console/integrations/git',
    },
    {
      icon: 'AI',
      title: 'Flexible LLMs',
      description: 'OpenAI, Anthropic, Gemini, Cursor, or custom OpenAI-compatible endpoints.',
      link: '/console/integrations/ai',
    },
    {
      icon: 'PR',
      title: 'Inline comments',
      description: 'Feedback anchored on changed lines with snippets and clear action items.',
      link: '/console/review',
    },
    {
      icon: '✉',
      title: 'Email alerts',
      description: 'Optional Gmail summaries when a review finishes.',
      link: '/console/integrations/notifications',
    },
  ];

  constructor(private readonly auth: AuthService) {}

  get signedIn(): boolean {
    return this.auth.isAuthenticated();
  }
}
