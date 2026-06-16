import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    @if (!ready) {
      <div class="login-shell">Loading...</div>
    } @else {
      <router-outlet />
    }
  `,
})
export class AppComponent implements OnInit {
  ready = false;

  constructor(private readonly auth: AuthService) {}

  async ngOnInit(): Promise<void> {
    try {
      await this.auth.ensureInitialized();
    } catch (err) {
      console.error('Auth initialization failed', err);
    } finally {
      this.ready = true;
    }
  }
}
