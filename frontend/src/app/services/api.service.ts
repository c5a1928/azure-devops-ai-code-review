import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import {
  GitConnection,
  GitConnectionInput,
  GitPlatformInfo,
  GitProject,
  GitProjectInput,
  LlmProviderInfo,
  ReviewJob,
  ReviewSettings,
  ReviewSettingsInput,
  TaskStatus,
} from '../models/types';
import { AuthLoginResponse, AuthStatus } from '../models/auth';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private readonly http: HttpClient) {}

  private headers(): HttpHeaders {
    return new HttpHeaders({ 'Content-Type': 'application/json' });
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    try {
      return await firstValueFrom(
        this.http.request<T>(method, path, {
          headers: this.headers(),
          body,
        }),
      );
    } catch (error: unknown) {
      const httpError = error as { error?: { detail?: string | { message?: string } } };
      const detail = httpError.error?.detail;
      if (typeof detail === 'string') {
        throw new Error(detail);
      }
      if (detail && typeof detail === 'object' && detail.message) {
        throw new Error(detail.message);
      }
      throw new Error('Request failed');
    }
  }

  authStatus(): Promise<AuthStatus> {
    return this.request<AuthStatus>('GET', '/api/auth/status');
  }

  login(password: string): Promise<AuthLoginResponse> {
    return this.request<AuthLoginResponse>('POST', '/api/auth/login', { password });
  }

  listPlatforms(): Promise<GitPlatformInfo[]> {
    return this.request<GitPlatformInfo[]>('GET', '/api/platforms');
  }

  listLlmProviders(): Promise<LlmProviderInfo[]> {
    return this.request<LlmProviderInfo[]>('GET', '/api/llm-providers');
  }

  getSettings(): Promise<ReviewSettings> {
    return this.request<ReviewSettings>('GET', '/api/settings');
  }

  saveSettings(payload: ReviewSettingsInput): Promise<ReviewSettings> {
    return this.request<ReviewSettings>('PUT', '/api/settings', payload);
  }

  listGitConnections(): Promise<GitConnection[]> {
    return this.request<GitConnection[]>('GET', '/api/git-connections');
  }

  createGitConnection(payload: GitConnectionInput): Promise<GitConnection> {
    return this.request<GitConnection>('POST', '/api/git-connections', payload);
  }

  updateGitConnection(id: number, payload: GitConnectionInput): Promise<GitConnection> {
    return this.request<GitConnection>('PUT', `/api/git-connections/${id}`, payload);
  }

  deleteGitConnection(id: number): Promise<void> {
    return this.request<void>('DELETE', `/api/git-connections/${id}`);
  }

  listGitProjects(): Promise<GitProject[]> {
    return this.request<GitProject[]>('GET', '/api/git-projects');
  }

  createGitProject(payload: GitProjectInput): Promise<GitProject> {
    return this.request<GitProject>('POST', '/api/git-projects', payload);
  }

  updateGitProject(id: number, payload: GitProjectInput): Promise<GitProject> {
    return this.request<GitProject>('PUT', `/api/git-projects/${id}`, payload);
  }

  deleteGitProject(id: number): Promise<void> {
    return this.request<void>('DELETE', `/api/git-projects/${id}`);
  }

  listJobs(): Promise<ReviewJob[]> {
    return this.request<ReviewJob[]>('GET', '/api/jobs');
  }

  getJob(taskId: string): Promise<ReviewJob> {
    return this.request<ReviewJob>('GET', `/api/jobs/${taskId}`);
  }

  startReview(payload: { pr_id: number; git_project_id: number }): Promise<{
    task_id: string;
    status: string;
    message: string;
  }> {
    return this.request('POST', '/api/review', payload);
  }

  getReviewStatus(taskId: string): Promise<TaskStatus> {
    return this.request<TaskStatus>('GET', `/api/review/${taskId}`);
  }
}
