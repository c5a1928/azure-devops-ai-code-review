import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { ReviewJob, REVIEW_STEP_LABELS } from '../../models/types';

@Component({
  selector: 'app-jobs-page',
  standalone: true,
  imports: [RouterLink, DatePipe, JsonPipe, FormsModule],
  template: `
    <div class="page-header">
      <h1>Jobs</h1>
      <p>Monitor review progress. Jobs keep running if you leave this page.</p>
    </div>

    <div class="card">
      @if (error) {
        <div class="alert error">{{ error }}</div>
      }
      @if (message) {
        <div class="alert success">{{ message }}</div>
      }

      <div class="jobs-toolbar">
        <label class="checkbox-field">
          <input type="checkbox" [(ngModel)]="showArchived" (ngModelChange)="onShowArchivedChange()" />
          Show archived
        </label>
      </div>

      @if (loading) {
        <p>Loading jobs...</p>
      } @else if (visibleJobs.length === 0) {
        <div class="alert warning">
          @if (showArchived) {
            No archived jobs.
          } @else {
            No review jobs yet.
            <a routerLink="/console/review">Start a review</a>
          }
        </div>
      } @else {
        <div class="project-list">
          @for (job of visibleJobs; track job.task_id) {
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
                  @if (job.archived_at) {
                    <span class="status-pill archived">archived</span>
                  }
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
              <div class="row-actions">
                <button class="secondary" type="button" (click)="toggleJob(job.task_id)">
                  {{ expandedJobId === job.task_id ? 'Hide' : 'Details' }}
                </button>
                @if (job.archived_at) {
                  <button
                    class="secondary"
                    type="button"
                    [disabled]="actingOnJobId === job.task_id"
                    (click)="unarchiveJob(job)"
                  >
                    Restore
                  </button>
                } @else {
                  <button
                    class="secondary"
                    type="button"
                    [disabled]="actingOnJobId === job.task_id"
                    (click)="archiveJob(job)"
                  >
                    Archive
                  </button>
                }
                <button
                  class="secondary danger"
                  type="button"
                  [disabled]="actingOnJobId === job.task_id"
                  (click)="deleteJob(job)"
                >
                  Delete
                </button>
              </div>
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
  message = '';
  showArchived = false;
  expandedJobId: string | null = null;
  actingOnJobId: string | null = null;
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private cancelled = false;

  constructor(
    private readonly api: ApiService,
    private readonly route: ActivatedRoute,
  ) {}

  get visibleJobs(): ReviewJob[] {
    if (this.showArchived) {
      return this.jobs.filter((job) => Boolean(job.archived_at));
    }
    return this.jobs.filter((job) => !job.archived_at);
  }

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

  async onShowArchivedChange(): Promise<void> {
    this.loading = true;
    await this.loadJobs();
    this.restartPolling();
  }

  async archiveJob(job: ReviewJob): Promise<void> {
    this.actingOnJobId = job.task_id;
    this.error = '';
    this.message = '';
    try {
      const updated = await this.api.archiveJob(job.task_id);
      this.jobs = this.jobs.map((item) => (item.task_id === updated.task_id ? updated : item));
      if (this.expandedJobId === job.task_id && !this.showArchived) {
        this.expandedJobId = null;
      }
      this.message = 'Job archived.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to archive job';
    } finally {
      this.actingOnJobId = null;
    }
  }

  async unarchiveJob(job: ReviewJob): Promise<void> {
    this.actingOnJobId = job.task_id;
    this.error = '';
    this.message = '';
    try {
      const updated = await this.api.unarchiveJob(job.task_id);
      this.jobs = this.jobs.map((item) => (item.task_id === updated.task_id ? updated : item));
      if (this.expandedJobId === job.task_id && this.showArchived) {
        this.expandedJobId = null;
      }
      this.message = 'Job restored.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to restore job';
    } finally {
      this.actingOnJobId = null;
    }
  }

  async deleteJob(job: ReviewJob): Promise<void> {
    const label = this.jobLabel(job);
    if (!window.confirm(`Delete job "${label}"? This cannot be undone.`)) {
      return;
    }
    this.actingOnJobId = job.task_id;
    this.error = '';
    this.message = '';
    try {
      await this.api.deleteJob(job.task_id);
      this.jobs = this.jobs.filter((item) => item.task_id !== job.task_id);
      if (this.expandedJobId === job.task_id) {
        this.expandedJobId = null;
      }
      this.message = 'Job deleted.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to delete job';
    } finally {
      this.actingOnJobId = null;
    }
  }

  private async loadJobs(): Promise<void> {
    try {
      this.jobs = await this.api.listJobs(this.showArchived);
      this.error = '';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load jobs';
    } finally {
      this.loading = false;
    }
  }

  private startPolling(): void {
    this.restartPolling();
  }

  private restartPolling(): void {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
    const poll = async () => {
      if (this.cancelled) return;
      await this.loadJobs();
      const hasActive = this.visibleJobs.some(
        (job) => job.status === 'pending' || job.status === 'in_progress',
      );
      if (!this.cancelled && hasActive && !this.showArchived) {
        this.pollTimer = setTimeout(poll, 2000);
      }
    };
    poll();
  }
}
