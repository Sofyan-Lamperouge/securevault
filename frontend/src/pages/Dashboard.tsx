// src/pages/Dashboard.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  getFiles,
  uploadFile,
  downloadFile,
  deleteFile,
  shareFile,
  shareFileMultiple,
  revokeAccess,
  getSharedWithMe,
  getActivities,
  previewFile,
} from '../services/api';
import { FileInfo, SharedFileInfo, ActivityInfo } from '../types';

const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [ownedFiles, setOwnedFiles] = useState<FileInfo[]>([]);
  const [sharedFiles, setSharedFiles] = useState<SharedFileInfo[]>([]);
  const [activities, setActivities] = useState<ActivityInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [shareUsername, setShareUsername] = useState('');
  const [sharePassword, setSharePassword] = useState('');
  const [activeTab, setActiveTab] = useState<'owned' | 'shared' | 'activities'>('owned');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewFilename, setPreviewFilename] = useState<string>('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewFileId, setPreviewFileId] = useState<number | null>(null);
  const [showShareMultipleModal, setShowShareMultipleModal] = useState(false);
  const [shareMultipleUsernames, setShareMultipleUsernames] = useState('');
  const [shareMultiplePassword, setShareMultiplePassword] = useState('');
  const [shareMultipleLoading, setShareMultipleLoading] = useState(false);

  const loadData = async () => {
    try {
      const [filesRes, sharedRes, activitiesRes] = await Promise.all([
        getFiles(),
        getSharedWithMe(),
        getActivities(),
      ]);
      setOwnedFiles(filesRes.data.owned);
      setSharedFiles(sharedRes.data);
      setActivities(activitiesRes.data);
    } catch (error) {
      toast.error('Gagal memuat data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    
    setUploading(true);
    for (const file of acceptedFiles) {
      try {
        await uploadFile(file);
        toast.success(`Berhasil diupload: ${file.name}`);
      } catch (error) {
        toast.error(`Gagal upload: ${file.name}`);
      }
    }
    setUploading(false);
    loadData();
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  const handleDownload = async (fileId: number, filename: string) => {
    const password = prompt('Masukkan password Anda untuk mendekripsi file:');
    if (!password) return;

    try {
      const response = await downloadFile(fileId, password);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('File berhasil didownload dan didekripsi!');
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      let message = 'Gagal download';
      if (detail === 'Invalid password') message = 'Password salah';
      else if (detail === 'File not found') message = 'File tidak ditemukan';
      else if (detail === 'Access denied') message = 'Akses ditolak';
      else if (detail) message = detail;
      toast.error(message);
    }
  };

  const handleDelete = async (fileId: number, filename: string) => {
    if (!window.confirm(`Hapus "${filename}"? Tindakan ini tidak dapat dibatalkan.`)) return;
    
    try {
      await deleteFile(fileId);
      toast.success(`Berhasil dihapus: ${filename}`);
      loadData();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      let message = 'Gagal hapus';
      if (detail === 'Only owner can delete this file') message = 'Hanya pemilik yang dapat menghapus file';
      else if (detail) message = detail;
      toast.error(message);
    }
  };

  const handleShare = async () => {
    if (!selectedFileId || !shareUsername || !sharePassword) {
      toast.error('Harap isi semua field');
      return;
    }

    try {
      await shareFile(selectedFileId, shareUsername, sharePassword);
      toast.success(`Berhasil dibagikan ke ${shareUsername}`);
      setShowShareModal(false);
      setShareUsername('');
      setSharePassword('');
      loadData();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      let message = 'Gagal share';
      if (detail === 'Target user not found') message = 'User target tidak ditemukan';
      else if (detail === 'Cannot share with yourself') message = 'Tidak bisa share ke diri sendiri';
      else if (detail === 'File already shared with this user') message = 'File sudah dishare ke user ini';
      else if (detail === 'Invalid password') message = 'Password salah';
      else if (detail) message = detail;
      toast.error(message);
    }
  };

  const handleShareMultiple = async () => {
    if (!selectedFileId || !shareMultipleUsernames || !shareMultiplePassword) {
      toast.error('Harap isi semua field');
      return;
    }

    const usernamesArray = shareMultipleUsernames
      .split(/[ ,]+/)
      .map(u => u.trim())
      .filter(u => u.length > 0);

    if (usernamesArray.length === 0) {
      toast.error('Masukkan minimal satu username');
      return;
    }

    setShareMultipleLoading(true);
    try {
      const response = await shareFileMultiple(selectedFileId, usernamesArray, shareMultiplePassword);
      const results = response.data.results;
      const successCount = results.filter((r: any) => r.status === 'success').length;
      const failCount = results.filter((r: any) => r.status === 'failed').length;
      
      if (failCount === 0) {
        toast.success(`Berhasil dibagikan ke ${successCount} user!`);
      } else {
        toast.success(`Dibagikan ke ${successCount} user, gagal: ${failCount}`);
        results.filter((r: any) => r.status === 'failed').forEach((r: any) => {
          toast.error(`${r.username}: ${r.reason}`);
        });
      }
      
      setShowShareMultipleModal(false);
      setShareMultipleUsernames('');
      setShareMultiplePassword('');
      loadData();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      toast.error(detail || 'Gagal share multiple');
    } finally {
      setShareMultipleLoading(false);
    }
  };

  const handleRevoke = async (fileId: number, username: string) => {
    if (!window.confirm(`Cabut akses untuk ${username}?`)) return;
    
    try {
      await revokeAccess(fileId, username);
      toast.success(`Akses dicabut untuk ${username}`);
      loadData();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Gagal cabut akses');
    }
  };

  const handlePreview = async (fileId: number, filename: string) => {
    const password = prompt('Masukkan password Anda untuk preview file:');
    if (!password) return;

    setPreviewLoading(true);
    setPreviewFileId(fileId);
    try {
      const response = await previewFile(fileId, password);
      const blob = response.data;
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
      setPreviewFilename(filename);
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      let message = 'Gagal preview';
      if (detail === 'Invalid password') message = 'Password salah';
      else if (detail === 'File not found') message = 'File tidak ditemukan';
      else if (detail === 'Access denied') message = 'Akses ditolak';
      else if (detail) message = detail;
      toast.error(message);
      setPreviewFileId(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      setPreviewFilename('');
      setPreviewFileId(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('id-ID');
  };

  const getActionText = (action: string) => {
    switch (action) {
      case 'UPLOAD': return 'UPLOAD';
      case 'DOWNLOAD': return 'DOWNLOAD';
      case 'SHARE': return 'SHARE';
      case 'PREVIEW': return 'PREVIEW';
      case 'REVOKE': return 'REVOKE';
      default: return action;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Memuat brankas aman Anda...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-primary-600">🔐 SecureVault</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">Selamat datang, {user?.username}</span>
            <button onClick={logout} className="btn-secondary">
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Area */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors mb-8
            ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'}`}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <p className="text-gray-500">Mengupload...</p>
          ) : isDragActive ? (
            <p className="text-primary-600">Lepas file di sini...</p>
          ) : (
            <p className="text-gray-500">Drag & drop file di sini, atau klik untuk pilih</p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-4 border-b border-gray-200 mb-6">
          <button
            onClick={() => setActiveTab('owned')}
            className={`pb-2 px-4 font-medium transition-colors ${
              activeTab === 'owned'
                ? 'text-primary-600 border-b-2 border-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            File Saya ({ownedFiles.length})
          </button>
          <button
            onClick={() => setActiveTab('shared')}
            className={`pb-2 px-4 font-medium transition-colors ${
              activeTab === 'shared'
                ? 'text-primary-600 border-b-2 border-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Dibagikan ke Saya ({sharedFiles.length})
          </button>
          <button
            onClick={() => setActiveTab('activities')}
            className={`pb-2 px-4 font-medium transition-colors ${
              activeTab === 'activities'
                ? 'text-primary-600 border-b-2 border-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Riwayat Aktivitas
          </button>
        </div>

        {/* My Files Tab */}
        {activeTab === 'owned' && (
          <div className="grid gap-4">
            {ownedFiles.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Belum ada file. Upload file pertama Anda!
              </div>
            ) : (
              ownedFiles.map((file) => (
                <div key={file.id} className="card p-4 flex items-center justify-between flex-wrap gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-900 truncate">{file.original_filename}</h3>
                    <p className="text-sm text-gray-500">
                      {formatFileSize(file.file_size)} • {formatDate(file.created_at)}
                    </p>
                    {file.shared_with.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {file.shared_with.map((username) => (
                          <span
                            key={username}
                            className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-full"
                          >
                            {username}
                            <button
                              onClick={() => handleRevoke(file.id, username)}
                              className="text-red-500 hover:text-red-700 ml-1 focus:outline-none"
                              title={`Cabut akses untuk ${username}`}
                            >
                              ✕
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDownload(file.id, file.original_filename)}
                      className="btn-primary text-sm py-1 px-3"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => handlePreview(file.id, file.original_filename)}
                      className="btn-secondary text-sm py-1 px-3"
                      disabled={previewLoading}
                    >
                      {previewLoading ? 'Memuat...' : 'Preview'}
                    </button>
                    <button
                      onClick={() => {
                        setSelectedFileId(file.id);
                        setShowShareModal(true);
                      }}
                      className="btn-secondary text-sm py-1 px-3"
                    >
                      Share
                    </button>
                    <button
                      onClick={() => {
                        setSelectedFileId(file.id);
                        setShowShareMultipleModal(true);
                      }}
                      className="btn-secondary text-sm py-1 px-3"
                    >
                      Share+
                    </button>
                    <button
                      onClick={() => handleDelete(file.id, file.original_filename)}
                      className="btn-danger text-sm py-1 px-3"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Shared Files Tab */}
        {activeTab === 'shared' && (
          <div className="grid gap-4">
            {sharedFiles.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Belum ada file yang dibagikan ke Anda.
              </div>
            ) : (
              sharedFiles.map((file) => (
                <div key={file.file_id} className="card p-4 flex items-center justify-between flex-wrap gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-900 truncate">{file.filename}</h3>
                    <p className="text-sm text-gray-500">
                      Dari: {file.owner} • {formatFileSize(file.file_size)} • {formatDate(file.shared_at)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDownload(file.file_id, file.filename)}
                      className="btn-primary text-sm py-1 px-3"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => handlePreview(file.file_id, file.filename)}
                      className="btn-secondary text-sm py-1 px-3"
                    >
                      Preview
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Activities Tab */}
        {activeTab === 'activities' && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Aksi</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">File</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Detail</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Waktu</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {activities.map((activity) => (
                  <tr key={activity.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        activity.action === 'UPLOAD' ? 'bg-green-100 text-green-800' :
                        activity.action === 'DOWNLOAD' ? 'bg-blue-100 text-blue-800' :
                        activity.action === 'SHARE' ? 'bg-purple-100 text-purple-800' :
                        activity.action === 'PREVIEW' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {getActionText(activity.action)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{activity.filename || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{activity.details}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{formatDate(activity.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* Preview Modal */}
      {previewUrl && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b">
              <h3 className="font-semibold text-gray-900">Preview: {previewFilename}</h3>
              <button
                onClick={closePreview}
                className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {previewFilename.match(/\.(jpg|jpeg|png|gif)$/i) ? (
                <img src={previewUrl} alt="Preview" className="max-w-full h-auto mx-auto" />
              ) : previewFilename.match(/\.(txt|md)$/i) ? (
                <iframe src={previewUrl} title="Preview" className="w-full h-[500px] border-0" />
              ) : previewFilename.match(/\.pdf$/i) ? (
                <iframe src={previewUrl} title="Preview" className="w-full h-[500px] border-0" />
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-500">Preview tidak tersedia untuk tipe file ini.</p>
                  <button
                    onClick={() => {
                      closePreview();
                      if (previewFileId) {
                        handleDownload(previewFileId, previewFilename);
                      }
                    }}
                    className="btn-primary mt-4"
                  >
                    Download saja
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {showShareModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">Share File</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Username penerima
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="contoh: kurumi"
                  value={shareUsername}
                  onChange={(e) => setShareUsername(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password Anda
                </label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="Diperlukan untuk dekripsi private key"
                  value={sharePassword}
                  onChange={(e) => setSharePassword(e.target.value)}
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={handleShare} className="btn-primary flex-1">
                  Share
                </button>
                <button
                  onClick={() => {
                    setShowShareModal(false);
                    setShareUsername('');
                    setSharePassword('');
                  }}
                  className="btn-secondary flex-1"
                >
                  Batal
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Share Multiple Modal */}
      {showShareMultipleModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">Share File ke Banyak User</h2>
            <p className="text-sm text-gray-500 mb-4">
              Masukkan username dipisah koma atau spasi
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="contoh: kurumi, alice, bob"
                  value={shareMultipleUsernames}
                  onChange={(e) => setShareMultipleUsernames(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password Anda
                </label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="Diperlukan untuk dekripsi private key"
                  value={shareMultiplePassword}
                  onChange={(e) => setShareMultiplePassword(e.target.value)}
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={handleShareMultiple} className="btn-primary flex-1" disabled={shareMultipleLoading}>
                  {shareMultipleLoading ? 'Memproses...' : 'Share ke Semua'}
                </button>
                <button
                  onClick={() => {
                    setShowShareMultipleModal(false);
                    setShareMultipleUsernames('');
                    setShareMultiplePassword('');
                  }}
                  className="btn-secondary flex-1"
                >
                  Batal
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;