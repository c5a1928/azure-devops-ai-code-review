import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { ReviewJob, REVIEW_STEP_LABELS } from '../../models/types';

@Component({
  selector: 'app-jobs-page',
  standalone: true,
  imports: [RouterLink, DatePipe, JsonPipe],
  template: `
    <div class="page-header">
      <h1>Jobs</h1>
      <p>Monitor review progress. Jobs keep running if you leave this page.</p>
    </div>

    <div class="card">
      @if (error) {
        <div class="alert error">{{ error }}</div>
      }

      @if (loading) {
        <p>Loading jobs...</p>
      } @else if (jobs.length === 0) {
        <div class="alert warning">
          No review jobs yet.
          <a routerLink="/console/review">Start a review</a>
        </div>
      } @else {
        <div class="project-list">
          @for (job of jobs; track job.task_id) {
            <div class="project-row job-row" [class.job-row-expanded]="expandedJobId === job.task_id">
              <div class="project-info">
                <div class="job-header">
                  <strong>{{ jobLabel(job) }}</strong>
                  <span
                    class="status-pill"
                    [class.ok]="job.status === 'completed'"
                    [class.bad]="job.status === 'failed'"
                    [class.pending]="job.status === 'pending' || job.status === 'in_progress'"
                  >
                    {{ statusLabel(job) }}
                  </span>
                </div>
                <span class="project-path">
                  {{ job.display_path }} ·
                  {{ job.platform === 'gitlab' ? 'MR' : 'PR' }} #{{ job.pr_id }}
                  · {{ job.created_at | date: 'short' }}
                </span>
                @if (stepLabel(job)) {
                  <span class="step-label">{{ stepLabel(job) }}</span>
                }
                @if (job.error) {
                  <span class="job-error">{{ job.error }}</span>
                }
              </div>
              <button class="secondary" type="button" (click)="toggleJob(job.task_id)">
                {{ expandedJobId === job.task_id ? 'Hide' : 'Details' }}
              </button>
            </div>
            @if (expandedJobId === job.task_id) {
              <div class="job-detail">
                @if (job.pr_url) {
                  <p><a [href]="job.pr_url" target="_blank" rel="noreferrer">Open pull request</a></p>
                }
                @if (job.title) {
                  <p><strong>Title:</strong> {{ job.title }}</p>
                }
                @if (job.verdict) {
                  <p><strong>Verdict:</strong> {{ job.verdict }}</p>
                }
                @if (job.result) {
                  <pre>{{ job.result | json }}</pre>
                }
              </div>
            }
          }
        </div>
      }
    </div>
  `,
})
export class JobsPageComponent implements OnInit, OnDestroy {
  jobs: ReviewJob[] = [];
  loading = true;
  error = '';
  expandedJobId: string | null = null;
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private cancelled = false;

  constructor(
    private readonly api: ApiService,
    private readonly route: ActivatedRoute,
  ) {}

  async ngOnInit(): Promise<void> {
    const highlight = this.route.snapshot.queryParamMap.get('job');
    if (highlight) {
      this.expandedJobId = highlight;
    }
    await this.loadJobs();
    this.startPolling();
  }

  ngOnDestroy(): void {
    this.cancelled = true;
    if (this.pollTimer) clearTimeout(this.pollTimer);
  }

  jobLabel(job: ReviewJob): string {
    if (job.title) {
      return job.title;
    }
    return `${job.repo_name} #${job.pr_id}`;
  }

  statusLabel(job: ReviewJob): string {
    return job.status.replace('_', ' ');
  }

  stepLabel(job: ReviewJob): string | null {
    if (job.status !== 'in_progress' || !job.step) {
      return null;
    }
    return REVIEW_STEP_LABELS[job.step] || job.step;
  }

  toggleJob(taskId: string): void {
    this.expandedJobId = this.expandedJobId === taskId ? null : taskId;
  }

  private async loadJobs(): Promise<void> {
    try {
      this.jobs = await this.api.listJobs();
      this.error = '';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load jobs';
    } finally {
      this.loading = false;
    }
  }

  private startPolling(): void {
    const poll = async () => {
      if (this.cancelled) return;
      await this.loadJobs();
      const hasActive = this.jobs.some(
        (job) => job.status === 'pending' || job.status === 'in_progress',
      );
      if (!this.cancelled && hasActive) {
        this.pollTimer = setTimeout(poll, 2000);
      }
    };
    poll();
  }
}
