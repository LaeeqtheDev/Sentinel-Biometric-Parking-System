/** Join class names while filtering out falsey values. */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}

/** Pretty timestamp for tables: "Aug 14, 14:32:05" */
export function fmtDateTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/** "2h 14m" style duration */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/* ------------- Domain types (mirror Django serializers) ------------- */

export interface UserVehicleAssignment {
  id: number;
  user: number;
  user_detail?: any;
  relationship: 'OWNER' | 'DRIVER' | 'BOTH';
  created_at: string;
}

export interface Vehicle {
  id: number;
  plate_number: string;
  vehicle_type: 'CAR' | 'BIKE' | 'SUV' | 'TRUCK' | 'OTHER';
  make: string;
  model: string;
  color: string;
  is_active: boolean;
  status: 'ACTIVE' | 'BLOCKED' | 'UNDER_REVIEW';
  block_reason?: string;
  assignments?: UserVehicleAssignment[];
  owners_detail?: any[];
  drivers_detail?: any[];
  created_at: string;
  updated_at: string;
}

export interface AccessLog {
  id: number;
  event_type: 'ENTRY' | 'EXIT';
  plate_detected: string;
  vehicle: number | null;
  vehicle_detail: any;
  user: number | null;
  user_detail: any;
  status: 'GRANTED' | 'DENIED' | 'PENDING';
  reason: string;
  plate_match: boolean;
  biometric_match: boolean;
  webauthn_match: boolean;
  biometric_distance: number | null;
  confidence: 'high' | 'medium' | 'low' | 'none';
  via: string;
  snapshot: string | null;
  timestamp: string;
}

export interface ParkingSession {
  id: number;
  vehicle: number;
  vehicle_detail: Vehicle;
  entry_user: number | null;
  entry_user_detail: any;
  exit_user: number | null;
  exit_user_detail: any;
  entry_log: number | null;
  exit_log: number | null;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  status: 'PARKED' | 'EXITED';
}

export interface Stats {
  totals: {
    all_time: number;
    granted: number;
    denied: number;
    today: number;
    today_granted: number;
    today_denied: number;
  };
  registered_vehicles: number;
  active_sessions?: number;
  last_7_days: { day: string; granted: number; denied: number }[];
  recent_logs: AccessLog[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface PasskeyCredential {
  id: number;
  credential_id_b64: string;
  nickname: string;
  transports: string[];
  created_at: string;
  last_used_at: string | null;
}
