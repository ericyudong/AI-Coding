export interface Instance {
  id: number;
  user_id: number;
  name: string;
  description?: string;
  type: 'openclaw' | 'ubuntu' | 'debian' | 'centos' | 'custom' | 'webtop';
  status: 'creating' | 'running' | 'stopped' | 'error' | 'deleting';
  cpu_cores: number;
  memory_gb: number;
  disk_gb: number;
  gpu_enabled: boolean;
  gpu_count: number;
  os_type: string;
  os_version: string;
  image_registry?: string;
  image_tag?: string;
  storage_class: string;
  mount_path: string;
  pod_name?: string;
  pod_namespace?: string;
  pod_ip?: string;
  access_url?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  stopped_at?: string;
}

export interface InstanceStatus {
  instance_id: number;
  status: string;
  pod_name?: string;
  pod_namespace?: string;
  pod_ip?: string;
  pod_status?: string;
  created_at: string;
  started_at?: string;
}

export interface CreateInstanceRequest {
  name: string;
  description?: string;
  type: 'openclaw' | 'ubuntu' | 'debian' | 'centos' | 'custom' | 'webtop';
  cpu_cores: number;
  memory_gb: number;
  disk_gb: number;
  gpu_enabled?: boolean;
  gpu_count?: number;
  os_type: string;
  os_version: string;
  image_registry?: string;
  image_tag?: string;
  storage_class?: string;
}

export interface UpdateInstanceRequest {
  name?: string;
  description?: string;
}

export interface InstanceListResponse {
  instances: Instance[];
  total: number;
  page: number;
  limit: number;
}

export interface InstanceType {
  id: string;
  name: string;
  description: string;
  icon: string;
  defaultOs: string;
  defaultVersion: string;
}

export const INSTANCE_TYPES: InstanceType[] = [
  {
    id: 'ubuntu',
    name: 'Ubuntu Desktop',
    description: 'Popular Linux distribution with GNOME desktop',
    icon: 'ubuntu',
    defaultOs: 'ubuntu',
    defaultVersion: '22.04'
  },
  {
    id: 'debian',
    name: 'Debian Desktop',
    description: 'Stable and secure Linux distribution',
    icon: 'debian',
    defaultOs: 'debian',
    defaultVersion: '12'
  },
  {
    id: 'centos',
    name: 'CentOS Desktop',
    description: 'Enterprise-class Linux distribution',
    icon: 'centos',
    defaultOs: 'centos',
    defaultVersion: '9'
  },
  {
    id: 'openclaw',
    name: 'OpenClaw Desktop',
    description: 'Optimized desktop environment',
    icon: 'openclaw',
    defaultOs: 'openclaw',
    defaultVersion: 'latest'
  },
  {
    id: 'webtop',
    name: 'Webtop Desktop',
    description: 'Browser-based Linux desktop proxied through ClawManager',
    icon: 'webtop',
    defaultOs: 'ubuntu',
    defaultVersion: 'xfce'
  },
  {
    id: 'custom',
    name: 'Custom Image',
    description: 'Use your own custom image',
    icon: 'custom',
    defaultOs: 'custom',
    defaultVersion: 'latest'
  }
];

export const PRESET_CONFIGS = {
  small: {
    name: 'Small',
    cpu_cores: 2,
    memory_gb: 4,
    disk_gb: 20,
    description: 'Suitable for light tasks'
  },
  medium: {
    name: 'Medium',
    cpu_cores: 4,
    memory_gb: 8,
    disk_gb: 50,
    description: 'Good for development'
  },
  large: {
    name: 'Large',
    cpu_cores: 8,
    memory_gb: 16,
    disk_gb: 100,
    description: 'For heavy workloads'
  }
};
