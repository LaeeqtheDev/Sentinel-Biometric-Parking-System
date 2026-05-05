'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ScanFace, CheckCircle2 } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { WebcamCapture } from '@/components/WebcamCapture';
import { apiGet, apiPost } from '@/lib/api';
import { User } from '@/lib/auth';

export default function EnrollBiometricPage() {
  const router = useRouter();
  const params = useParams();
  const userId = params.id as string;

  const [user, setUser] = useState<User | null>(null);
  const [capture, setCapture] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [enrolled, setEnrolled] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<User>(`/auth/users/${userId}/`)
      .then((u) => {
        setUser(u);
        setEnrolled(u.has_biometric);
      })
      .catch((e) => setError(e.message));
  }, [userId]);

  async function enroll() {
    if (!capture) return;
    setSubmitting(true);
    setError('');
    try {
      await apiPost('/biometrics/enroll/', {
        user_id: Number(userId),
        image_base64: capture,
      });
      setEnrolled(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Topbar
        title="Biometric Enrollment"
        subtitle={user ? `For ${user.first_name || user.username}` : ''}
      />

      <main className="flex-1 p-6 lg:p-8">
        <Link
          href="/dashboard/users"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-bone-500 transition-colors hover:text-bone-300"
        >
          <ArrowLeft className="size-3.5" /> Back to users
        </Link>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-5">
          {/* Info panel */}
          <aside className="space-y-4 lg:col-span-2">
            <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
              <div className="mb-3 grid size-10 place-items-center rounded-md bg-amber/10 text-amber">
                <ScanFace className="size-5" />
              </div>
              <h2 className="font-display text-lg font-semibold text-bone-50">
                Capture face encoding
              </h2>
              <p className="mt-2 text-sm text-bone-400">
                The system extracts a 128-dimensional vector from the user's
                face. This vector — not the photo — is used during entry
                verification.
              </p>
              <ul className="mt-5 space-y-2 text-xs text-bone-500">
                <li>· Look directly at the camera</li>
                <li>· Ensure even, frontal lighting</li>
                <li>· Remove sunglasses or face coverings</li>
                <li>· Keep a neutral expression</li>
              </ul>
            </div>

            {user && (
              <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
                <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
                  User
                </p>
                <p className="mt-2 text-base text-bone-100">
                  {user.first_name} {user.last_name}
                </p>
                <p className="font-mono text-xs text-bone-500">
                  @{user.username} · {user.role}
                </p>
                <div className="mt-3 flex items-center gap-2">
                  {enrolled ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-granted/40 bg-granted/10 px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-granted">
                      <CheckCircle2 className="size-3" /> Enrolled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-ink-600 bg-ink-700/40 px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-bone-400">
                      Not enrolled
                    </span>
                  )}
                </div>
              </div>
            )}
          </aside>

          {/* Capture */}
          <div className="lg:col-span-3">
            <WebcamCapture
              onCapture={setCapture}
              showOverlay
              aspect="4:3"
              label="Capture face"
              preview={capture}
            />

            {error && (
              <div className="mt-4 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                {error}
              </div>
            )}

            {enrolled ? (
              <div className="mt-4 rounded-lg border border-granted/40 bg-granted/10 p-4">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="size-6 text-granted" />
                  <div>
                    <p className="font-medium text-granted">Biometric enrolled</p>
                    <p className="text-xs text-bone-400">
                      The user can now be authenticated at the gate.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setEnrolled(false);
                      setCapture(null);
                    }}
                  >
                    Re-enroll
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => router.push('/dashboard/users')}
                  >
                    Done — back to users
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  variant="primary"
                  size="lg"
                  disabled={!capture}
                  loading={submitting}
                  onClick={enroll}
                >
                  Save biometric
                </Button>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
