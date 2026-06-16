import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import {
  CUSTOM_BASE_URL_VALUE,
  GitConnection,
  GitConnectionInput,
  GitPlatformInfo,
  PLATFORM_ICONS,
} from '../../models/types';

const CUSTOM_BASE_URL = CUSTOM_BASE_URL_VALUE;

@Component({
  selector: 'app-git-integration-page',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="page-header">
      <h1>Git platform</h1>
      <p>Add one or more git platform connections. Projects are linked to a connection when you create them.</p>
    </div>

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
          <div class="alert warning">No git platforms configured yet. Add your first connection below.</div>
        } @else {
          <div class="project-list">
            @for (connection of connections; track connection.id) {
              <div class="project-row">
                <div class="project-info">
                  <strong>{{ connection.display_name }}</strong>
                  <span class="project-path">{{ connection.owner }} · {{ connection.base_url }}</span>
                </div>
                <button
                  class="secondary"
                  type="button"
                  [disabled]="deletingConnectionId === connection.id"
                  (click)="removeConnection(connection)"
                >
                  {{ deletingConnectionId === connection.id ? 'Removing...' : 'Remove' }}
                </button>
              </div>
            }
          </div>
        }
      </div>

      <div class="card">
        <h2>Add git platform</h2>
        <p class="subtitle">Choose a provider and enter connection details.</p>

        <div class="platform-grid">
          @for (platform of platforms; track platform.id) {
            <button
              type="button"
              class="platform-card"
              [class.selected]="newConnection.platform === platform.id"
              (click)="selectPlatform(platform)"
            >
              <div class="platform-icon">{{ iconFor(platform.id) }}</div>
              <h3>{{ platform.name }}</h3>
              <p>{{ platform.default_base_url }}</p>
            </button>
          }
        </div>

        @if (selectedPlatform) {
          <form (ngSubmit)="addConnection()">
            <div class="section-title">Connection</div>
            <div class="grid-2">
              <div class="field">
                <label for="connectionLabel">Nickname (optional)</label>
                <input
                  id="connectionLabel"
                  [(ngModel)]="newConnection.label"
                  name="connectionLabel"
                  placeholder="e.g. Production ADO"
                />
              </div>
              <div class="field">
                <label for="baseUrlPreset">API base URL</label>
                <select
                  id="baseUrlPreset"
                  [(ngModel)]="baseUrlSelection"
                  name="baseUrlPreset"
                  (ngModelChange)="onBaseUrlSelectionChange()"
                >
                  @for (option of selectedPlatform.base_url_options; track option.url) {
                    <option [value]="option.url">{{ option.label }}</option>
                  }
                  <option [value]="customBaseUrlValue">Custom URL...</option>
                </select>
              </div>
              @if (baseUrlSelection === customBaseUrlValue) {
                <div class="field">
                  <label for="baseUrlCustom">Custom API base URL</label>
                  <textarea
                    id="baseUrlCustom"
                    class="url-input"
                    rows="2"
                    [(ngModel)]="customBaseUrl"
                    name="baseUrlCustom"
                    placeholder="https://your-instance.example.com/api"
                    required
                  ></textarea>
                </div>
              }
              <div class="field">
                <label for="owner">{{ selectedPlatform.owner_label }}</label>
                <input
                  id="owner"
                  [(ngModel)]="newConnection.owner"
                  name="owner"
                  [placeholder]="ownerPlaceholder"
                  required
                />
                @if (newConnection.platform === 'azure_devops') {
                  <small>Your Azure DevOps organization name (e.g. contoso).</small>
                }
              </div>
              <div class="field">
                <label for="token">{{ selectedPlatform.token_label }}</label>
                <input
                  id="token"
                  type="password"
                  [(ngModel)]="newConnection.token"
                  name="token"
                  required
                />
              </div>
            </div>
            <div class="actions">
              <button class="primary" type="submit" [disabled]="saving">
                {{ saving ? 'Adding...' : 'Add git platform' }}
              </button>
            </div>
          </form>
        }
      </div>
    }
  `,
})
export class GitIntegrationPageComponent implements OnInit {
  readonly customBaseUrlValue = CUSTOM_BASE_URL;

  platforms: GitPlatformInfo[] = [];
  connections: GitConnection[] = [];
  newConnection: GitConnectionInput = {
    label: '',
    platform: 'azure_devops',
    base_url: 'https://dev.azure.com',
    owner: '',
    token: '',
  };
  baseUrlSelection = 'https://dev.azure.com';
  customBaseUrl = '';
  loading = true;
  saving = false;
  deletingConnectionId: number | null = null;
  error = '';
  message = '';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
  ) {}

  get selectedPlatform(): GitPlatformInfo | undefined {
    return this.platforms.find((platform) => platform.id === this.newConnection.platform);
  }

  get ownerPlaceholder(): string {
    if (this.newConnection.platform === 'azure_devops') {
      return 'e.g. contoso';
    }
    if (this.newConnection.platform === 'github') {
      return 'e.g. my-org';
    }
    if (this.newConnection.platform === 'gitlab') {
      return 'e.g. my-group';
    }
    return '';
  }

  iconFor(id: string): string {
    return PLATFORM_ICONS[id] || 'GT';
  }

  async ngOnInit(): Promise<void> {
    try {
      const [platforms, connections] = await Promise.all([
        this.api.listPlatforms(),
        this.api.listGitConnections(),
      ]);
      this.platforms = platforms;
      this.connections = connections;
      if (platforms.length > 0) {
        this.selectPlatform(platforms[0]);
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load git platforms';
    } finally {
      this.loading = false;
    }
  }

  selectPlatform(platform: GitPlatformInfo): void {
    this.newConnection.platform = platform.id;
    this.newConnection.base_url = platform.default_base_url;
    this.baseUrlSelection = platform.default_base_url;
    this.customBaseUrl = '';
  }

  onBaseUrlSelectionChange(): void {
    if (this.baseUrlSelection === CUSTOM_BASE_URL) {
      this.newConnection.base_url = this.customBaseUrl;
      return;
    }
    this.newConnection.base_url = this.baseUrlSelection;
    this.customBaseUrl = '';
  }

  private resolvedBaseUrl(): string {
    if (this.baseUrlSelection === CUSTOM_BASE_URL) {
      return this.customBaseUrl.trim();
    }
    return this.baseUrlSelection.trim();
  }

  async addConnection(): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    this.saving = true;
    this.error = '';
    this.message = '';
    try {
      const created = await this.api.createGitConnection({
        ...this.newConnection,
        base_url: this.resolvedBaseUrl(),
        label: this.newConnection.label.trim(),
        owner: this.newConnection.owner.trim(),
        token: this.newConnection.token.trim(),
      });
      this.connections = [...this.connections, created];
      this.newConnection = {
        label: '',
        platform: this.newConnection.platform,
        base_url: this.newConnection.base_url,
        owner: '',
        token: '',
      };
      this.message = 'Git platform added.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to add git platform';
    } finally {
      this.saving = false;
    }
  }

  async removeConnection(connection: GitConnection): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    this.deletingConnectionId = connection.id;
    this.error = '';
    this.message = '';
    try {
      await this.api.deleteGitConnection(connection.id);
      this.connections = this.connections.filter((item) => item.id !== connection.id);
      this.message = 'Git platform removed.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to remove git platform';
    } finally {
      this.deletingConnectionId = null;
    }
  }
}
