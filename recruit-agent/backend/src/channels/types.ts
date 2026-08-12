export type PublishJobInput = {
  job: {
    id: string;
    title: string;
    workLocation?: string | null;
    responsibilities?: string | null;
    requirements?: string | null;
    publishCopy?: string | null;
    salaryMin?: number | null;
    salaryMax?: number | null;
  };
  account?: { accountName?: string; externalId?: string | null; mappingJson?: string | null } | null;
  channelCode: string;
};

export type OutreachInput = {
  channelCode: string;
  jobId: string;
  jobTitle?: string;
  candidateId: string;
  candidateName?: string;
  message: string;
  account?: { accountName?: string; externalId?: string | null } | null;
  externalCandidateRef?: string;
};

export type AdapterResult = {
  ok: boolean;
  mode: 'sandbox' | 'live';
  externalRef?: string | null;
  message: string;
  raw?: unknown;
};

export interface ChannelAdapter {
  code: string;
  name: string;
  health(): Promise<{ ok: boolean; mode: 'sandbox' | 'live'; detail?: string }>;
  publishJob(input: PublishJobInput): Promise<AdapterResult>;
  sendGreeting(input: OutreachInput): Promise<AdapterResult>;
}
