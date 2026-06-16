export interface KeycloakAuthConfig {
  url: string;
  realm: string;
  client_id: string;
}

export interface AuthStatus {
  auth_required: boolean;
  provider: 'keycloak' | 'password' | 'none';
  keycloak: KeycloakAuthConfig | null;
}

export interface AuthLoginResponse {
  access_token: string;
  auth_required: boolean;
}
