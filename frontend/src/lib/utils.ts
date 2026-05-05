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

/** Convert "fbbf24" hex to rgba string with alpha. */
export function hexToRgba(hex: string, alpha = 1): string {
  const h = hex.replace('#', '');
  const bigint = parseInt(h, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* ------------- Domain types (mirror Django serializers) ------------- */

export interface Vehicle {
  id: number;
  owner: number;
  owner_detail?: any;
  plate_number: string;
  vehicle_type: 'CAR' | 'BIKE' | 'SUV' | 'TRUCK' | 'OTHER';
  make: string;
  model: string;
  color: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AccessLog {
  id: number;
  plate_detected: string;
  vehicle: number | null;
  vehicle_detail: any;
  user: number | null;
  user_detail: any;
  status: 'GRANTED' | 'DENIED' | 'PENDING';
  reason: string;
  plate_match: boolean;
  biometric_match: boolean;
  biometric_distance: number | null;
  snapshot: string | null;
  timestamp: string;
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
  last_7_days: { day: string; granted: number; denied: number }[];
  recent_logs: AccessLog[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
