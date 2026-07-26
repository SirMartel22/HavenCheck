export interface Hostel {
  id: string;
  name: string;
  location: string;
  priceNaira: number;
  amenities: string[];
  description: string;
  photo_url: string | null;
  lat: number | null;
  lng: number | null;
  isSchoolManaged: boolean;
  scamRiskLevel: string | null;
  utility_reports?: UtilityReport[];
}

export interface UtilityReport {
  id: number;
  hostel_id: string;
  water_available: boolean;
  electricity_issue: boolean;
  comment: string;
  reported_at: string | null;
}

export interface AgentToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface AgentResponse {
  reply: string | null;
  tool_used: string | null;
  tool_calls: AgentToolCall[];
}

export interface ChatMessage {
  id: number;
  sessionId: string;
  hostelId: string | null;
  role: "user" | "assistant";
  content: string;
  createdAt: string | null;
}

export interface VoiceChatResponse {
  transcript: string;
  reply: string | null;
  tool_used: string | null;
  tool_calls: AgentToolCall[];
  audioBase64: string | null;
  audioContentType: string | null;
  voiceError: string | null;
}

interface ApiEnvelope<T> {
  message: string;
  data: T;
  action: null | { type: string; url?: string };
  error: null | { code: string; details: unknown };
}

export const demoHostels: Hostel[] = [
  {
    id: "hostel-tanke-01",
    name: "Harmony Lodge",
    location: "Tanke",
    priceNaira: 150000,
    amenities: ["borehole", "prepaid meter", "study lounge"],
    description: "Quiet block near campus with steady power and fast water access.",
    photo_url: "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
    lat: 8.4799,
    lng: 4.5418,
    isSchoolManaged: false,
    scamRiskLevel: "low",
    utility_reports: [
      {
        id: 1,
        hostel_id: "hostel-tanke-01",
        water_available: true,
        electricity_issue: false,
        comment: "Water runs early mornings and power stays stable.",
        reported_at: "2026-07-20T09:00:00+00:00",
      },
    ],
  },
  {
    id: "hostel-tanke-02",
    name: "Silver Court",
    location: "Tanke",
    priceNaira: 180000,
    amenities: ["generator", "security", "wifi"],
    description: "A newer property with strong security and a slightly higher budget.",
    photo_url: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=900&q=80",
    lat: 8.4812,
    lng: 4.5445,
    isSchoolManaged: true,
    scamRiskLevel: "medium",
    utility_reports: [],
  },
  {
    id: "hostel-sabo-01",
    name: "Avenue House",
    location: "Sabo",
    priceNaira: 125000,
    amenities: ["shared kitchen", "parking", "balcony"],
    description: "Budget-friendly option with a calm environment and a few shared facilities.",
    photo_url: "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=900&q=80",
    lat: 8.4891,
    lng: 4.5511,
    isSchoolManaged: false,
    scamRiskLevel: "low",
    utility_reports: [],
  },
];

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_LIVE_BE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_LIVE_BE_URL_2
)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.message ?? "Request failed");
  }

  return payload as T;
}

export async function getHostels(location?: string, maxPrice?: number): Promise<Hostel[]> {
  const params = new URLSearchParams();
  if (location) params.set("location", location);
  if (maxPrice) params.set("maxPrice", String(maxPrice));

  try {
    const payload = await request<ApiEnvelope<{ hostels: Hostel[] }>>(`/hostels${params.toString() ? `?${params.toString()}` : ""}`);
    return payload.data?.hostels ?? [];
  } catch {
    return demoHostels.filter((hostel) => {
      const matchesLocation = !location || hostel.location.toLowerCase() === location.toLowerCase();
      const matchesPrice = !maxPrice || hostel.priceNaira <= maxPrice;
      return matchesLocation && matchesPrice;
    });
  }
}

export async function getHostel(hostelId: string): Promise<Hostel | null> {
  try {
    const payload = await request<ApiEnvelope<{ hostel: Hostel }>>(`/hostels/${hostelId}`);
    return payload.data?.hostel ?? null;
  } catch {
    return demoHostels.find((item) => item.id === hostelId) ?? null;
  }
}

export async function getReports(hostelId: string): Promise<UtilityReport[]> {
  try {
    const payload = await request<ApiEnvelope<{ reports: UtilityReport[] }>>(`/hostels/${hostelId}/reports`);
    return payload.data?.reports ?? [];
  } catch {
    return demoHostels.find((item) => item.id === hostelId)?.utility_reports ?? [];
  }
}

export async function createReport(hostelId: string, payload: { water_available: boolean; electricity_issue: boolean; comment: string }) {
  return request<ApiEnvelope<{ report: UtilityReport }>>(`/hostels/${hostelId}/reports`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function notifyAuthority(hostelId: string, issueType: string, details: string) {
  return request<ApiEnvelope<{ status: string }>>(`/hostels/${hostelId}/notify-authority`, {
    method: "POST",
    body: JSON.stringify({ issueType, details }),
  });
}

export async function alertSecurity(hostelId: string, reason: string, evidence: string) {
  return request<ApiEnvelope<{ status: string }>>(`/hostels/${hostelId}/alert-security`, {
    method: "POST",
    body: JSON.stringify({ reason, evidence }),
  });
}

export async function createHostel(payload: Record<string, unknown>) {
  return request<ApiEnvelope<{ hostel: Hostel }>>(`/hostels`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getChatHistory(sessionId: string, hostelId?: string): Promise<ChatMessage[]> {
  const params = new URLSearchParams({ sessionId });
  if (hostelId) params.set("hostelId", hostelId);

  const payload = await request<ApiEnvelope<{ messages: ChatMessage[] }>>(`/chat/history?${params.toString()}`);
  return payload.data?.messages ?? [];
}

export async function sendAgentMessage(message: string, hostelId?: string, sessionId = "demo-session") {
  const payload = await request<ApiEnvelope<{ reply: string | null; tool_used: string | null; tool_calls: AgentToolCall[] }>>(`/agent`, {
    method: "POST",
    body: JSON.stringify({ message, hostelId, sessionId }),
  });
  return payload.data;
}

export async function sendVoiceMessage(audio: Blob, hostelId?: string, sessionId = "demo-session", speakReply = true): Promise<VoiceChatResponse> {
  const formData = new FormData();
  formData.append("audio", audio, "recording.webm");
  formData.append("sessionId", sessionId);
  formData.append("speakReply", String(speakReply));
  if (hostelId) formData.append("hostelId", hostelId);

  const response = await fetch(`${API_BASE}/voice/chat`, {
    method: "POST",
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.message ?? "Voice chat request failed");
  }

  return (payload?.data as VoiceChatResponse) ?? {
    transcript: "",
    reply: null,
    tool_used: null,
    tool_calls: [],
    audioBase64: null,
    audioContentType: null,
    voiceError: null,
  };
}
