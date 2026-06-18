import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import {
  CUSTOM_BASE_URL_VALUE,
  CUSTOM_MODEL_VALUE,
  LLM_PROVIDER_ICONS,
  LlmProviderInfo,
  ReviewSettings,
  ReviewSettingsInput,
  SECRET_PLACEHOLDER,
  mergeLlmProviders,
  toSettingsForm,
} from '../../models/types';

@Component({
  selector: 'app-ai-integration-page',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="page-header">
      <h1>AI model</h1>
      <p>Configure the LLM provider used to generate code reviews.</p>
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

        <h2>Select provider</h2>
        <p class="subtitle">Choose the model family that powers your reviews.</p>

        <div class="platform-grid">
          @for (provider of providers; track provider.id) {
            <button
              type="button"
              class="platform-card"
              [class.selected]="form.llm_provider === provider.id"
              (click)="selectProvider(provider)"
            >
              <div class="platform-icon">{{ iconFor(provider.id) }}</div>
              <h3>{{ provider.name }}</h3>
              <p>{{ providerSummary(provider) }}</p>
            </button>
          }
        </div>

        @if (selectedProvider) {
          <form (ngSubmit)="save()">
            <div class="section-title">Connection</div>
            <div class="grid-2">
              @if (selectedProvider.base_url_options.length > 0) {
                <div class="field">
                  <label for="openaiBaseUrlPreset">API base URL</label>
                  <select
                    id="openaiBaseUrlPreset"
                    [(ngModel)]="baseUrlSelection"
                    name="openaiBaseUrlPreset"
                    (ngModelChange)="onBaseUrlSelectionChange()"
                  >
                    @for (option of selectedProvider.base_url_options; track option.url) {
                      <option [value]="option.url">{{ option.label }}</option>
                    }
                    <option [value]="customBaseUrlValue">Custom URL...</option>
                  </select>
                </div>
              }
              @if (
                (selectedProvider.id === 'custom' || baseUrlSelection === customBaseUrlValue) &&
                selectedProvider.id !== 'cursor'
              ) {
                <div class="field">
                  <label for="openaiBaseUrlCustom">Custom API base URL</label>
                  <textarea
                    id="openaiBaseUrlCustom"
                    class="url-input"
                    rows="2"
                    [(ngModel)]="customBaseUrl"
                    name="openaiBaseUrlCustom"
                    placeholder="https://your-llm-provider.example.com/v1"
                    required
                  ></textarea>
                  <small>Enter the full OpenAI-compatible API root URL.</small>
                </div>
              }
              @if (selectedProvider.model_options.length > 0) {
                <div class="field">
                  <label for="openaiModelPreset">Model</label>
                  <select
                    id="openaiModelPreset"
                    [(ngModel)]="modelSelection"
                    name="openaiModelPreset"
                    (ngModelChange)="onModelSelectionChange()"
                  >
                    @for (option of selectedProvider.model_options; track option.id) {
                      <option [value]="option.id">{{ option.label }}</option>
                    }
                    <option [value]="customModelValue">Custom model...</option>
                  </select>
                </div>
              }
              @if (
                selectedProvider.id === 'custom' || modelSelection === customModelValue
              ) {
                <div class="field">
                  <label for="openaiModelCustom">Custom model ID</label>
                  <input
                    id="openaiModelCustom"
                    [(ngModel)]="customModel"
                    name="openaiModelCustom"
                    placeholder="provider/model-id"
                    required
                  />
                  <small>Use the exact model slug your API provider expects.</small>
                </div>
              }
              <div class="field">
                <label for="openaiKey">{{ selectedProvider.token_label }}</label>
                <input
                  id="openaiKey"
                  type="password"
                  [(ngModel)]="apiKeyInput"
                  name="openaiKey"
                  [placeholder]="status?.openai_api_key_masked || 'Paste API key'"
                />
                @if (status?.openai_api_key_configured) {
                  <small>Configured: {{ status?.openai_api_key_masked }}</small>
                }
                @if (selectedProvider.id === 'cursor') {
                  <small>
                    Create a key in
                    <a href="https://cursor.com/dashboard" target="_blank" rel="noreferrer">
                      Cursor Dashboard → Integrations
                    </a>
                    . Uses the Cursor Agent API (not OpenAI).
                  </small>
                }
              </div>
              @if (selectedProvider.id === 'openai') {
                <div class="field">
                  <label for="reasoningEffort">Reasoning effort</label>
                  <select
                    id="reasoningEffort"
                    [(ngModel)]="form.openai_reasoning_effort"
                    name="reasoningEffort"
                  >
                    <option [ngValue]="null">Disabled</option>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                    <option value="xhigh">xhigh</option>
                  </select>
                </div>
              }
              <div class="field">
                <label for="maxTokens">Max tokens</label>
                <input
                  id="maxTokens"
                  type="number"
                  min="1024"
                  [(ngModel)]="form.openai_max_tokens"
                  name="maxTokens"
                />
              </div>
              @if (selectedProvider.id !== 'openai' && selectedProvider.id !== 'cursor') {
                <div class="field">
                  <label for="temperature">Temperature</label>
                  <input
                    id="temperature"
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    [(ngModel)]="form.openai_temperature"
                    name="temperature"
                  />
                  <small>Used when reasoning effort is disabled.</small>
                </div>
              }
            </div>

            <div class="actions">
              <button class="primary" type="submit" [disabled]="saving">
                {{ saving ? 'Saving...' : 'Save AI settings' }}
              </button>
            </div>
          </form>
        }
      </div>
    }
  `,
})
export class AiIntegrationPageComponent implements OnInit {
  readonly customBaseUrlValue = CUSTOM_BASE_URL_VALUE;
  readonly customModelValue = CUSTOM_MODEL_VALUE;

  providers: LlmProviderInfo[] = [];
  form!: ReviewSettingsInput;
  status: ReviewSettings | null = null;
  apiKeyInput = '';
  baseUrlSelection = '';
  customBaseUrl = '';
  modelSelection = '';
  customModel = '';
  loading = true;
  saving = false;
  error = '';
  message = '';

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
  ) {}

  get selectedProvider(): LlmProviderInfo | undefined {
    return this.providers.find((provider) => provider.id === this.form.llm_provider);
  }

  iconFor(id: string): string {
    return LLM_PROVIDER_ICONS[id] || 'AI';
  }

  providerSummary(provider: LlmProviderInfo): string {
    if (provider.id === 'cursor') {
      return 'Cursor Agent API';
    }
    if (provider.id === 'custom') {
      return 'Any OpenAI-compatible endpoint';
    }
    return provider.default_base_url || provider.default_model;
  }

  async ngOnInit(): Promise<void> {
    try {
      const [providers, settings] = await Promise.all([
        this.api.listLlmProviders(),
        this.api.getSettings(),
      ]);
      this.providers = mergeLlmProviders(providers);
      this.status = settings;
      this.form = toSettingsForm(settings);
      this.syncBaseUrlSelection();
      this.syncModelSelection();
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load settings';
    } finally {
      this.loading = false;
    }
  }

  selectProvider(provider: LlmProviderInfo): void {
    this.form.llm_provider = provider.id;
    this.form.openai_base_url = provider.default_base_url;
    this.form.openai_model = provider.default_model;
    if (provider.id !== 'openai') {
      this.form.openai_reasoning_effort = null;
    }
    if (provider.id === 'cursor') {
      this.form.openai_base_url = '';
    }
    this.syncBaseUrlSelection();
    this.syncModelSelection();
  }

  onBaseUrlSelectionChange(): void {
    if (this.baseUrlSelection === CUSTOM_BASE_URL_VALUE) {
      this.form.openai_base_url = this.customBaseUrl;
      return;
    }
    this.form.openai_base_url = this.baseUrlSelection;
    this.customBaseUrl = '';
  }

  onModelSelectionChange(): void {
    if (this.modelSelection === CUSTOM_MODEL_VALUE) {
      this.form.openai_model = this.customModel;
      return;
    }
    this.form.openai_model = this.modelSelection;
    this.customModel = '';
  }

  private syncModelSelection(): void {
    const provider = this.selectedProvider;
    if (!provider) {
      return;
    }
    if (provider.id === 'custom') {
      this.modelSelection = CUSTOM_MODEL_VALUE;
      this.customModel = this.form.openai_model;
      return;
    }
    const match = provider.model_options.find((option) => option.id === this.form.openai_model);
    if (match) {
      this.modelSelection = match.id;
      this.customModel = '';
      return;
    }
    this.modelSelection = CUSTOM_MODEL_VALUE;
    this.customModel = this.form.openai_model;
  }

  private resolvedModel(): string {
    if (this.selectedProvider?.id === 'custom' || this.modelSelection === CUSTOM_MODEL_VALUE) {
      return this.customModel.trim();
    }
    return this.modelSelection.trim();
  }

  private syncBaseUrlSelection(): void {
    const provider = this.selectedProvider;
    if (!provider) {
      return;
    }
    if (provider.id === 'cursor') {
      this.baseUrlSelection = '';
      this.customBaseUrl = '';
      return;
    }
    if (provider.id === 'custom') {
      this.baseUrlSelection = CUSTOM_BASE_URL_VALUE;
      this.customBaseUrl = this.form.openai_base_url;
      return;
    }
    const match = provider.base_url_options.find(
      (option) => option.url === this.form.openai_base_url,
    );
    if (match) {
      this.baseUrlSelection = match.url;
      this.customBaseUrl = '';
      return;
    }
    this.baseUrlSelection = CUSTOM_BASE_URL_VALUE;
    this.customBaseUrl = this.form.openai_base_url;
  }

  private resolvedBaseUrl(): string {
    if (this.selectedProvider?.id === 'cursor') {
      return '';
    }
    if (this.selectedProvider?.id === 'custom' || this.baseUrlSelection === CUSTOM_BASE_URL_VALUE) {
      return this.customBaseUrl.trim();
    }
    return this.baseUrlSelection.trim();
  }

  async save(): Promise<void> {
    if (!this.auth.requireAuthForAction(this.router.url)) {
      return;
    }
    this.saving = true;
    this.error = '';
    this.message = '';
    try {
      const current = await this.api.getSettings();
      const payload: ReviewSettingsInput = {
        ...toSettingsForm(current),
        ...this.form,
        openai_base_url: this.resolvedBaseUrl(),
        openai_model: this.resolvedModel(),
        openai_api_key:
          this.apiKeyInput || (this.status?.openai_api_key_configured ? SECRET_PLACEHOLDER : ''),
        git_token: current.git_token_configured ? SECRET_PLACEHOLDER : '',
        gmail_app_password: current.gmail_app_password_configured ? SECRET_PLACEHOLDER : '',
      };
      this.status = await this.api.saveSettings(payload);
      this.form = toSettingsForm(this.status);
      this.syncBaseUrlSelection();
      this.syncModelSelection();
      this.apiKeyInput = '';
      this.message = 'AI settings saved.';
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      this.saving = false;
    }
  }
}
