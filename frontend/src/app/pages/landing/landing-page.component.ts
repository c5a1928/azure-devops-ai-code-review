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
          <img src="favicon-32x32.png" alt="" class="brand-logo" width="28" height="28" />
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

      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">AI-powered pull request reviews</p>
          <h1>Ship better code with automated, context-aware PR reviews</h1>
          <p class="hero-lead">
            Connect your git platform, choose an LLM, and get senior-engineer quality feedback
            posted directly on your pull requests — inline comments, work-item context, and
            framework-aware analysis.
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
              Explore features
            </a>
          </div>
          <p class="hero-note">No account needed to explore. Sign in only when you're ready to run a review.</p>
        </div>
        <div class="hero-panel card">
          <h3>What you get</h3>
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
          <h2>Built for real engineering teams</h2>
          <p>Browse integrations and settings without signing in. Configure when you're ready.</p>
        </div>
        <div class="feature-grid">
          @for (feature of features; track feature.title) {
            <a [routerLink]="feature.link" class="feature-card card">
              <div class="feature-icon">{{ feature.icon }}</div>
              <h3>{{ feature.title }}</h3>
              <p>{{ feature.description }}</p>
              <span class="feature-link">Explore →</span>
            </a>
          }
        </div>
      </section>

      <section id="how-it-works" class="section section-muted">
        <div class="section-heading">
          <h2>How it works</h2>
          <p>From connection to comments in three steps.</p>
        </div>
        <ol class="steps">
          <li class="step card">
            <span class="step-num">1</span>
            <div>
              <h3>Connect your git platform</h3>
              <p>Azure DevOps, GitHub, GitLab, or Bitbucket — cloud or self-hosted.</p>
            </div>
          </li>
          <li class="step card">
            <span class="step-num">2</span>
            <div>
              <h3>Choose your AI model</h3>
              <p>OpenAI, Anthropic, Gemini, Llama, or any OpenAI-compatible API.</p>
            </div>
          </li>
          <li class="step card">
            <span class="step-num">3</span>
            <div>
              <h3>Run a review</h3>
              <p>Sign in, enter a PR ID, and let the LLM post actionable inline feedback.</p>
            </div>
          </li>
        </ol>
      </section>

      <section class="section cta-section">
        <div class="cta-card card">
          <h2>Ready to review your next pull request?</h2>
          <p>Sign in when you want to queue a review. Exploring integrations is always free.</p>
          <div class="hero-cta">
            <a
              routerLink="/login"
              [queryParams]="{ returnUrl: '/console/review' }"
              class="button-link primary large"
            >
              Sign in to run a review
            </a>
            <a routerLink="/console/integrations/git" class="button-link secondary large">
              Browse integrations
            </a>
          </div>
        </div>
      </section>

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
      icon: '⌥',
      title: 'Multi-platform git',
      description:
        'Azure DevOps, GitHub, GitLab, and Bitbucket with presets for cloud and self-hosted URLs.',
      link: '/console/integrations/git',
    },
    {
      icon: '✦',
      title: 'Flexible LLM providers',
      description:
        'OpenAI, Anthropic, Gemini, Llama, or custom endpoints — pick models per provider.',
      link: '/console/integrations/ai',
    },
    {
      icon: '▶',
      title: 'Inline PR comments',
      description:
        'Reviews post directly on changed lines with code snippets and clear, actionable feedback.',
      link: '/console/review',
    },
    {
      icon: '✉',
      title: 'Email notifications',
      description: 'Optional Gmail summaries when a review finishes so your team stays in the loop.',
      link: '/console/integrations/notifications',
    },
  ];

  constructor(private readonly auth: AuthService) {}

  get signedIn(): boolean {
    return this.auth.isAuthenticated();
  }
}
