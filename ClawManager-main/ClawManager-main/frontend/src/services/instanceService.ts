import api from './api';
import type { 
  Instance, 
  InstanceListResponse, 
  CreateInstanceRequest, 
  UpdateInstanceRequest,
  InstanceStatus 
} from '../types/instance';

export const instanceService = {
  // Get instance list
  getInstances: async (page: number = 1, limit: number = 20): Promise<InstanceListResponse> => {
    const response = await api.get('/instances', {
      params: { page, limit }
    });
    return response.data.data;
  },

  // Create instance
  createInstance: async (data: CreateInstanceRequest): Promise<Instance> => {
    const response = await api.post('/instances', data);
    return response.data.data;
  },

  // Get instance by ID
  getInstance: async (id: number): Promise<Instance> => {
    const response = await api.get(`/instances/${id}`);
    return response.data.data;
  },

  // Update instance
  updateInstance: async (id: number, data: UpdateInstanceRequest): Promise<void> => {
    await api.put(`/instances/${id}`, data);
  },

  // Delete instance
  deleteInstance: async (id: number): Promise<void> => {
    await api.delete(`/instances/${id}`);
  },

  // Start instance
  startInstance: async (id: number): Promise<void> => {
    await api.post(`/instances/${id}/start`);
  },

  // Stop instance
  stopInstance: async (id: number): Promise<void> => {
    await api.post(`/instances/${id}/stop`);
  },

  // Restart instance
  restartInstance: async (id: number): Promise<void> => {
    await api.post(`/instances/${id}/restart`);
  },

  // Force sync instance status
  forceSyncInstance: async (id: number): Promise<void> => {
    await api.post(`/instances/${id}/sync`);
  },

  // Get instance status
  getInstanceStatus: async (id: number): Promise<InstanceStatus> => {
    const response = await api.get(`/instances/${id}/status`);
    return response.data.data;
  },

  // Generate access token
  generateAccessToken: async (id: number): Promise<{
    token: string;
    access_url: string;
    proxy_url: string;
    expires_at: string;
  }> => {
    const response = await api.post(`/instances/${id}/access`);
    return response.data.data;
  },

  // Access instance with token
  getAccessUrl: (id: number, token: string): string => {
    return `/api/v1/instances/${id}/access?token=${token}`;
  },

  exportOpenClawWorkspace: async (id: number): Promise<Blob> => {
    const response = await api.get(`/instances/${id}/openclaw/export`, {
      responseType: 'blob',
    });
    return response.data;
  },

  importOpenClawWorkspace: async (id: number, file: File): Promise<void> => {
    const formData = new FormData();
    formData.append('file', file);
    await api.post(`/instances/${id}/openclaw/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }
};
