import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import {
  GitConnection,
  GitPlatformInfo,
  GitProject,
  GitProjectInput,
} from '../../models/types';

@Component({
  selector: 'app-projects-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <p class="page-lead">Repositories to review, each linked to a configured git platform.</p>

    @if (loading) {
      <div class="card">Loading...</div>
    } @else {
      <div class="card">
        @if (error) {
          <div class="alert error">{{ error }}</div>
        }
        @if (message) {
          <div class="alert success">{{ message }}</div>
        }

        @if (connections.length === 0) {
          <div class="alert warning">
            Add a git platform first.
            <a routerLink="/console/integrations/git">Configure git platform</a>
          </div>
        }

        @if (projects.length === 0 && connections.length > 0) {
          <div class="alert warning">No projects configured yet. Add at least one to run reviews.</div>
        }

        @if (projects.length > 0) {
          <div class="project-list">
            @for (project of projects; track project.id) {
              <div class="project-row">
                <div class="project-info">
                  <strong>{{ projectDisplayName(project) }}</strong>
                  <span class="project-path">
                    {{ project.git_connection_label || project.platform }} · {{ project.display_path }}
                  </span>
                </div>
                <div class="row-actions">
                  <button class="secondary" type="button" (click)="startEditProject(project)">
                    Edit
                  </button>
                  <button
                    class="secondary"
                    type="button"
                    [disabled]="deletingProjectId === project.id"
                    (click)="removeProject(project)"
                  >
                    {{ deletingProjectId === project.id ? 'Removing...' : 'Remove' }}
                  </button>
                </div>
              </div>
            }
          </div>
        }

        @if (connections.length > 0) {
          <form class="project-form" (ngSubmit)="saveProject()">
            <div class="section-title">{{ editingProjectId ? 'Edit project' : 'Add project' }}</div>
            <div class="grid-2">
              <div class="field">
                <label for="gitConnection">Git platform</label>
                <select
                  id="gitConnection"
                  [(ngModel)]="newProject.git_connection_id"
                  name="gitConnection"
                  (ngModelChange)="onConnectionChange()"
                  required
                >
                  <option [ngValue]="0" disabled>Select a git platform</option>
                  @for (connection of connections; track connection.id) {
                    <option [ngValue]="connection.id">{{ connection.display_name }}</option>
                  }
                </select>
              </div>
              <div class="field">
                <label for="projectLabel">Nickname (optional)</label>
                <input
                  id="projectLabel"
                  [(ngModel)]="newProject.label"
                  name="projectLabel"
                  placeholder="e.g. Payments API"
                />
              </div>
              @if (selectedConnection && isAzureDevOps) {
                <div class="field">
                  <label for="organization">Organization</label>
                  @if (selectedConnection.owner) {
                    <input
                      id="organization"
                      [value]="selectedConnection.owner"
                      name="organization"
                      readonly
                    />
                    <small>From the selected git platform connection.</small>
                  } @else {
                    <div class="alert warning" style="margin: 0;">
                      Organization is missing on this connection.
                      <a routerLink="/console/integrations/git">Update git platform</a>
                    </div>
                  }
                </div>
                <div class="field">
                  <label for="newProjectName">Project</label>
                  <input
                    id="newProjectName"
                    [(ngModel)]="newProject.project"
                    name="newProjectName"
                    placeholder="e.g. Avire Hub"
                    required
                  />
                </div>
              } @else if (selectedPlatform?.id === 'gitlab') {
                <div class="field">
                  <label for="newSubgroup">{{ selectedPlatform?.project_label }}</label>
                  <input
                    id="newSubgroup"
                    [(ngModel)]="newProject.project"
                    name="newSubgroup"
                    placeholder="e.g. platform (optional)"
                  />
                </div>
              }
              <div class="field">
                <label for="newRepo">{{ selectedPlatform?.repo_label || 'Repository' }}</label>
                <input
                  id="newRepo"
                  [(ngModel)]="newProject.repo"
                  name="newRepo"
                  [required]="selectedPlatform?.repo_required ?? true"
                  placeholder="my-service"
                  [disabled]="!newProject.git_connection_id"
                />
              </div>
            </div>
            <div class="actions">
              @if (editingProjectId) {
                <button class="secondary" type="button" [disabled]="savingProject" (click)="cancelEditProject()">
                  Cancel
                </button>
              }
              <button
                class="primary"
                type="submit"
                [disabled]="savingProject || !newProject.git_connection_id"
              >
                {{
                  savingProject
                    ? editingProjectId
                      ? 'Saving...'
                      : 'Adding...'
                    : editingProjectId
                      ? 'Save changes'
                      : 'Add project'
                }}
              </button>
            </div>
          </form>
        }
      </div>
    }
  `,
})
export class ProjectsPageComponent implements OnInit {
  platforms: GitPlatformInfo[] = [];
  connections: GitConnection[] = [];
  projects: GitProject[] = [];
  newProject: GitProjectInput = {
    git_connection_id: 0,
    label: '',
    project: '',
    repo: '',
  };
  loading = true;
  savingProject = false;
  deletingProjectId: number | null = null;
  editingProjectId: number | null = null;
  error = '';
  message = '';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
  ) {}

  get selectedConnection(): GitConnection | undefined {
    return this.connections.find(
      (connection) => connection.id === this.newProject.git_connection_id,
    );
  }

  get selectedPlatform(): GitPlatformInfo | undefined {
    const connection = this.selectedConnection;
    if (!connection) {
      return undefined;
    }
    return this.platforms.find((platform) => platform.id === connection.platform);
  }

  get isAzureDevOps(): boolean {
    return this.selectedConnection?.platform === 'azure_devops';
  }

  projectDisplayName(project: GitProject): string {
    return project.label || project.repo;
  }

  async ngOnInit(): Promise<void> {
    try {
      const [platforms, connections, projects] = await Promise.all([
        this.api.listPlatforms(),
        this.api.listGitConnections(),
        this.api.listGitProjects(),
      ]);
      this.platforms = platforms;
      this.connections = connections;
      this.projects = projects;
      if (connections.length === 1) {
        this.newProject.git_connection_id = connections[0].id;
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load projects';
    } finally {
      this.loading = false;
    }
  }

  onConnectionChange(): void {
    this.newProject.project = '';
    this.newProject.repo = '';
  }

  async saveProject(): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    if (!this.newProject.git_connection_id) {
      return;
    }
    this.savingProject = true;
    this.error = '';
    this.message = '';
    try {
      const payload: GitProjectInput = {
        git_connection_id: this.newProject.git_connection_id,
        label: this.newProject.label.trim(),
        project: this.newProject.project.trim(),
        repo: this.newProject.repo.trim(),
      };
      if (this.editingProjectId) {
        const updated = await this.api.updateGitProject(this.editingProjectId, payload);
        this.projects = this.projects.map((item) => (item.id === updated.id ? updated : item));
        this.cancelEditProject();
        this.message = 'Project updated.';
      } else {
        const created = await this.api.createGitProject(payload);
        this.projects = [...this.projects, created];
        this.resetNewProjectForm();
        this.message = 'Project added.';
      }
    } catch (err) {
      this.error =
        err instanceof Error
          ? err.message
          : this.editingProjectId
            ? 'Failed to update project'
            : 'Failed to add project';
    } finally {
      this.savingProject = false;
    }
  }

  startEditProject(project: GitProject): void {
    this.editingProjectId = project.id;
    this.newProject = {
      git_connection_id: project.git_connection_id,
      label: project.label,
      project: project.project,
      repo: project.repo,
    };
    this.error = '';
    this.message = '';
  }

  cancelEditProject(): void {
    this.editingProjectId = null;
    this.resetNewProjectForm();
    this.error = '';
  }

  private resetNewProjectForm(): void {
    this.newProject = {
      git_connection_id: this.connections.length === 1 ? this.connections[0].id : 0,
      label: '',
      project: '',
      repo: '',
    };
  }

  async removeProject(project: GitProject): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    this.deletingProjectId = project.id;
    this.error = '';
    this.message = '';
    try {
      await this.api.deleteGitProject(project.id);
      this.projects = this.projects.filter((item) => item.id !== project.id);
      this.message = 'Project removed.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to remove project';
    } finally {
      this.deletingProjectId = null;
    }
  }
}
