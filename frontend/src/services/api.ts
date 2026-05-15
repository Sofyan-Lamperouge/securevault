// src/services/api.ts

import axios from 'axios';
import { FileListResponse, ShareInfo, SharedFileInfo, ActivityInfo } from '../types';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor untuk menambahkan token ke setiap request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ==================== Auth Endpoints ====================
export const register = (username: string, email: string, password: string) =>
  api.post('/auth/register', { username, email, password });

export const login = (username: string, password: string) =>
  api.post('/auth/login', { username, password });

export const getCurrentUser = () => api.get('/auth/me');

// ==================== File Endpoints ====================
export const uploadFile = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getFiles = () => api.get<FileListResponse>('/files/');

export const downloadFile = (fileId: number, password: string) =>
  api.get(`/files/download/${fileId}`, {
    params: { password },
    responseType: 'blob',
  });

export const deleteFile = (fileId: number) =>
  api.delete(`/files/${fileId}`);

export const previewFile = (fileId: number, password: string) =>
  api.get(`/files/preview/${fileId}`, {
    params: { password },
    responseType: 'blob',
  });

// ==================== Share Endpoints ====================
export const shareFile = (fileId: number, targetUsername: string, password: string, accessType: string = 'read_only') =>
  api.post(`/share/${fileId}?password=${password}`, {
    target_username: targetUsername,
    access_type: accessType,
  });

export const shareFileMultiple = (fileId: number, targetUsernames: string[], password: string) =>
  api.post(`/share/${fileId}/share-multiple?password=${password}`, {
    target_usernames: targetUsernames,
    access_type: 'read_only',
  });

export const getMyShares = () => api.get<ShareInfo[]>('/share/my-shares');

export const getSharedWithMe = () => api.get<SharedFileInfo[]>('/share/shared-with-me');

export const revokeAccess = (fileId: number, username: string) =>
  api.delete(`/share/${fileId}/user/${username}`);

export const checkAccess = (fileId: number) =>
  api.get(`/share/check-access/${fileId}`);

// ==================== Activity Endpoints ====================
export const getActivities = (limit: number = 50) =>
  api.get<ActivityInfo[]>(`/activity/?limit=${limit}`);