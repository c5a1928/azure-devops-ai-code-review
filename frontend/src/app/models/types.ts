export const SECRET_PLACEHOLDER = '__UNCHANGED__';

export interface BaseUrlOption {
  label: string;
  url: string;
}

export interface ModelOption {
  label: string;
  id: string;
}

export interface GitPlatformInfo {
  id: string;
  name: string;
  default_base_url: string;
  base_url_options: BaseUrlOption[];
  owner_label: string;
  project_label: string;
  repo_label: string;
  token_label: string;
  project_required: boolean;
  repo_required: boolean;
}

export interface LlmProviderInfo {
  id: string;
  name: string;
  default_base_url: string;
  default_model: string;
  base_url_options: BaseUrlOption[];
  model_options: ModelOption[];
  token_label: string;
}

/** Ensures Cursor appears in the AI provider picker even on older API builds. */
export const CURSOR_LLM_PROVIDER: LlmProviderInfo = {
  id: 'cursor',
  name: 'Cursor',
  default_base_url: '',
  default_model: 'composer-2.5',
  base_url_options: [],
  model_options: [
    { label: 'Composer 2.5 — recommended', id: 'composer-2.5' },
    { label: 'Composer 2', id: 'composer-2' },
    { label: 'GPT-5.4', id: 'gpt-5.4' },
    { label: 'Claude Sonnet 4.6', id: 'claude-sonnet-4.6' },
  ],
  token_label: 'Cursor API key',
};

const LLM_PROVIDER_ORDER = ['openai', 'cursor', 'anthropic', 'gemini', 'llama', 'custom'] as const;

export function mergeLlmProviders(providers: LlmProviderInfo[]): LlmProviderInfo[] {
  const byId = new Map(providers.map((provider) => [provider.id, provider]));
  if (!byId.has('cursor')) {
    byId.set('cursor', CURSOR_LLM_PROVIDER);
  }
  return LLM_PROVIDER_ORDER.map((id) => byId.get(id)).filter(
    (provider): provider is LlmProviderInfo => provider !== undefined,
  );
}

export interface ReviewSettings {
  git_platform: string;
  git_base_url: string;
  git_owner: string;
  git_default_project: string;
  git_default_repo: string;
  git_token_configured: boolean;
  git_token_masked: string | null;
  llm_provider: string;
  openai_api_key_configured: boolean;
  openai_api_key_masked: string | null;
  openai_base_url: string;
  openai_model: string;
  openai_temperature: number;
  openai_max_tokens: number;
  openai_reasoning_effort: string | null;
  gmail_user: string;
  gmail_app_password_configured: boolean;
  gmail_app_password_masked: string | null;
  git_project_count: number;
  git_connection_count: number;
  configured: boolean;
  missing_fields: string[];
}

export interface GitConnection {
  id: number;
  label: string;
  platform: string;
  platform_name: string;
  base_url: string;
  owner: string;
  token_configured: boolean;
  token_masked: string | null;
  display_name: string;
}

export interface GitConnectionInput {
  label: string;
  platform: string;
  base_url: string;
  owner: string;
  token: string;
}

export interface GitProject {
  id: number;
  git_connection_id: number;
  git_connection_label: string;
  platform: string;
  label: string;
  project: string;
  repo: string;
  display_path: string;
}

export interface GitProjectInput {
  git_connection_id: number;
  label: string;
  project: string;
  repo: string;
}

export interface ReviewSettingsInput {
  git_platform: string;
  git_base_url: string;
  git_owner: string;
  git_default_project: string;
  git_default_repo: string;
  git_token: string;
  llm_provider: string;
  openai_api_key: string;
  openai_base_url: string;
  openai_model: string;
  openai_temperature: number;
  openai_max_tokens: number;
  openai_reasoning_effort: string | null;
  gmail_user: string;
  gmail_app_password: string;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  result?: Record<string, unknown>;
  error?: string;
}

export interface ReviewJob {
  task_id: string;
  git_project_id: number;
  display_path: string;
  platform: string;
  repo_name: string;
  pr_id: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  step?: string | null;
  error?: string | null;
  pr_url?: string | null;
  title?: string | null;
  verdict?: string | null;
  result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  archived_at?: string | null;
}

export const REVIEW_STEP_LABELS: Record<string, string> = {
  fetching_pr: 'Fetching pull request',
  resolving_comments: 'Resolving prior comments',
  reviewing: 'Running LLM review',
  posting_comments: 'Posting comments',
  sending_email: 'Sending notification email',
};

export const EMPTY_SETTINGS_FORM: ReviewSettingsInput = {
  git_platform: 'azure_devops',
  git_base_url: 'https://dev.azure.com',
  git_owner: '',
  git_default_project: '',
  git_default_repo: '',
  git_token: '',
  llm_provider: 'openai',
  openai_api_key: '',
  openai_base_url: 'https://api.openai.com/v1',
  openai_model: 'gpt-5.5',
  openai_temperature: 0,
  openai_max_tokens: 16384,
  openai_reasoning_effort: 'high',
  gmail_user: '',
  gmail_app_password: '',
};

export function toSettingsForm(settings: ReviewSettings): ReviewSettingsInput {
  return {
    git_platform: settings.git_platform,
    git_base_url: settings.git_base_url,
    git_owner: settings.git_owner,
    git_default_project: settings.git_default_project,
    git_default_repo: settings.git_default_repo,
    git_token: settings.git_token_configured ? SECRET_PLACEHOLDER : '',
    llm_provider: settings.llm_provider,
    openai_api_key: settings.openai_api_key_configured ? SECRET_PLACEHOLDER : '',
    openai_base_url: settings.openai_base_url,
    openai_model: settings.openai_model,
    openai_temperature: settings.openai_temperature,
    openai_max_tokens: settings.openai_max_tokens,
    openai_reasoning_effort: settings.openai_reasoning_effort,
    gmail_user: settings.gmail_user,
    gmail_app_password: settings.gmail_app_password_configured ? SECRET_PLACEHOLDER : '',
  };
}

export const PLATFORM_ICONS: Record<string, string> = {
  azure_devops: 'AD',
  github: 'GH',
  gitlab: 'GL',
  bitbucket: 'BB',
};

export const LLM_PROVIDER_ICONS: Record<string, string> = {
  openai: 'OA',
  cursor: 'CU',
  anthropic: 'AN',
  gemini: 'GM',
  llama: 'LL',
  custom: 'CU',
};

export const CUSTOM_BASE_URL_VALUE = '__custom__';
export const CUSTOM_MODEL_VALUE = '__custom_model__';
