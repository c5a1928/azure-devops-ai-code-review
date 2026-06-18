import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { GitProject, ReviewSettings } from '../../models/types';

@Component({
  selector: 'app-review-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <h1>Run review</h1>
      <p>Select a configured project and enter a {{ prIdLabel }} to queue an AI review.</p>
    </div>

    <div class="card">
      @if (settings && !settings.configured) {
        <div class="alert warning">
          Configuration is incomplete.
          <a routerLink="/console/integrations/git">Configure git platform</a>
          @if (needsAi) {
            and <a routerLink="/console/integrations/ai">AI model</a>
          }
          @if (needsProjects) {
            and <a routerLink="/console/projects">add projects</a>
          }
        </div>
      }
      @if (error) {
        <div class="alert error">{{ error }}</div>
      }
      @if (queuedMessage) {
        <div class="alert success">
          {{ queuedMessage }}
          <a routerLink="/console/jobs">View jobs</a>
        </div>
      }

      @if (settings) {
        <div class="help review-target">
          <div><strong>Projects:</strong> {{ projects.length }} configured</div>
        </div>
      }

      @if (projects.length === 0) {
        <div class="alert warning">
          No projects configured.
          <a routerLink="/console/projects">Add projects</a> on the Projects page.
        </div>
      }

      <form (ngSubmit)="handleSubmit()">
        <div class="grid-2">
          <div class="field">
            <label for="gitProject">Project</label>
            <select id="gitProject" [(ngModel)]="selectedProjectId" name="gitProject" required>
              <option [ngValue]="null" disabled>Select a project</option>
              @for (project of projects; track project.id) {
                <option [ngValue]="project.id">{{ projectOptionLabel(project) }}</option>
              }
            </select>
          </div>
          <div class="field">
            <label for="prId">{{ prIdLabel }}</label>
            <input id="prId" type="number" min="1" [(ngModel)]="prId" name="prId" required />
          </div>
        </div>
        @if (selectedProject) {
          <p class="help">
            Target: <strong>{{ selectedProject.display_path }}</strong>
            ({{ selectedProject.git_connection_label || selectedProject.platform }})
          </p>
        }
        <div class="actions">
          <button
            class="primary"
            type="submit"
            [disabled]="submitting || !settings?.configured || !selectedProjectId"
          >
            {{ submitting ? 'Queueing...' : 'Start review' }}
          </button>
        </div>
      </form>
    </div>
  `,
})
export class ReviewPageComponent implements OnInit {
  settings: ReviewSettings | null = null;
  projects: GitProject[] = [];
  selectedProjectId: number | null = null;
  prId: number | null = null;
  error = '';
  queuedMessage = '';
  submitting = false;

  constructor(
    private readonly api: ApiService,
    private readonly router: Router,
  ) {}

  get prIdLabel(): string {
    return this.selectedProject?.platform === 'gitlab' ? 'Merge request ID' : 'Pull request ID';
  }

  get selectedProject(): GitProject | undefined {
    if (this.selectedProjectId === null) return undefined;
    return this.projects.find((project) => project.id === this.selectedProjectId);
  }

  get needsAi(): boolean {
    return Boolean(
      this.settings?.missing_fields.some(
        (field) => field === 'openai_api_key' || field === 'cursor_api_key',
      ),
    );
  }

  get needsProjects(): boolean {
    return Boolean(this.settings?.missing_fields.includes('git_projects'));
  }

  projectOptionLabel(project: GitProject): string {
    const prefix = project.git_connection_label || project.platform;
    if (project.label) {
      return `${project.label} · ${prefix} · ${project.display_path}`;
    }
    return `${prefix} · ${project.display_path}`;
  }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, projects] = await Promise.all([
        this.api.getSettings(),
        this.api.listGitProjects(),
      ]);
      this.settings = settings;
      this.projects = projects;
      if (projects.length === 1) {
        this.selectedProjectId = projects[0].id;
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load settings';
    }
  }

  async handleSubmit(): Promise<void> {
    if (this.prId === null || this.selectedProjectId === null) return;
    this.submitting = true;
    this.error = '';
    this.queuedMessage = '';
    try {
      const response = await this.api.startReview({
        pr_id: Number(this.prId),
        git_project_id: this.selectedProjectId,
      });
      void this.router.navigate(['/console/jobs'], {
        queryParams: { job: response.task_id },
      });
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to start review';
    } finally {
      this.submitting = false;
    }
  }
}
