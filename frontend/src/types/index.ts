// src/types/index.ts

export interface User {
  id: number;
  username: string;
  email: string;
  public_key_pem: string;
}

export interface FileInfo {
  id: number;
  original_filename: string;
  file_size: number;
  file_hash: string;
  created_at: string;
  is_owner: boolean;
  shared_with: string[];
}

export interface FileListResponse {
  owned: FileInfo[];
  shared_with_me: FileInfo[];
}

export interface ShareInfo {
  file_id: number;
  filename: string;
  shared_with: string;
  access_type: string;
  shared_at: string;
}

export interface SharedFileInfo {
  file_id: number;
  filename: string;
  owner: string;
  file_size: number;
  shared_at: string;
}

export interface ActivityInfo {
  id: number;
  action: string;
  file_id: number;
  filename: string | null;
  target_user: string | null;
  details: string;
  created_at: string;
}