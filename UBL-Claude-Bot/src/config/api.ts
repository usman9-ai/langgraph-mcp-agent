const rawApiBaseUrl = import.meta.env.VITE_API_URL;

if (!rawApiBaseUrl) {
  throw new Error('VITE_API_URL is not set. Please add it to your .env file.');
}

export const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, '');

export const buildApiUrl = (path: string): string => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};
