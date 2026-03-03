import { buildApiUrl } from '../config/api';

const LOGIN_URL = buildApiUrl('/auth/login');

export interface LoginResponse {
  access_token: string;
}

export async function loginRequest(employeeId: string, password: string): Promise<LoginResponse> {
  const response = await fetch(LOGIN_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ employee_id: employeeId, password }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let message = 'Unable to login. Please try again.';

    try {
      const parsed = JSON.parse(errorBody);
      const detail = parsed.detail || parsed.message || '';
      if (response.status === 401) {
        message = 'Wrong Credentials';
      } else if (response.status === 403) {
        message = 'Not Authorized';
      } else {
        message = detail || message;
      }
    } catch {
      if (errorBody) {
        message = errorBody;
      }
    }

    throw new Error(message);
  }

  return response.json();
}
