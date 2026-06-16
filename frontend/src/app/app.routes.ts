import { Routes } from '@angular/router';
import { authGuard } from './auth.guard';
import { LayoutComponent } from './layout/layout.component';
import { LandingPageComponent } from './pages/landing/landing-page.component';
import { LoginPageComponent } from './pages/login/login-page.component';
import { JobsPageComponent } from './pages/jobs/jobs-page.component';
import { ReviewPageComponent } from './pages/review/review-page.component';
import { ProjectsPageComponent } from './pages/projects/projects-page.component';
import { GitIntegrationPageComponent } from './pages/integrations/git-integration-page.component';
import { AiIntegrationPageComponent } from './pages/integrations/ai-integration-page.component';
import { NotificationsPageComponent } from './pages/integrations/notifications-page.component';

export const routes: Routes = [
  { path: '', component: LandingPageComponent },
  { path: 'login', component: LoginPageComponent },
  {
    path: 'console',
    component: LayoutComponent,
    children: [
      { path: 'review', component: ReviewPageComponent, canActivate: [authGuard] },
      { path: 'jobs', component: JobsPageComponent, canActivate: [authGuard] },
      { path: 'projects', component: ProjectsPageComponent },
      { path: 'integrations/git', component: GitIntegrationPageComponent },
      { path: 'integrations/ai', component: AiIntegrationPageComponent },
      { path: 'integrations/notifications', component: NotificationsPageComponent },
      { path: '', redirectTo: 'review', pathMatch: 'full' },
      { path: '**', redirectTo: 'review' },
    ],
  },
  { path: '**', redirectTo: '' },
];
