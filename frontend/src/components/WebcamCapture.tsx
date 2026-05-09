'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import Webcam from 'react-webcam';
import {
  Camera,
  RotateCcw,
  Check,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { Button } from './Button';
import { cn } from '@/lib/utils';

interface Props {
  /** Called whenever the user accepts a capture (or clears it). */
  onCapture: (imageDataUrl: string | null) => void;
  /** Current value (controlled). Synonym for `preview`. */
  value?: string | null;
  /** Backwards-compat alias for value. */
  preview?: string | null;
  /** Aspect ratio: '4:3' | '16:9' | 'square' */
  aspect?: '4:3' | '16:9' | 'square';
  /** Show the scanning grid overlay (face-recognition look) */
  showOverlay?: boolean;
  /** Label on the capture button. */
  label?: string;
  /** Hint text shown above the camera. */
  placeholder?: string;
  /** Use the back-facing ("environment") camera. Default: front-facing. */
  facing?: 'user' | 'environment';
  /** Reject captures whose blur score is below this threshold. */
  minSharpness?: number;
}

/**
 * Estimate how sharp an image is using a Laplacian-like operator.
 * Higher = sharper. Returns 0..∞ (typical good ≈ 100+, bad < 30).
 *
 * Done client-side via a hidden canvas so we can warn the user and reject
 * blurry frames BEFORE we send them to the backend.
 */
function estimateSharpness(dataUrl: string): Promise<number> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      // Downscale for speed
      const scale = Math.min(1, 320 / Math.max(img.width, img.height));
      canvas.width = Math.max(64, Math.floor(img.width * scale));
      canvas.height = Math.max(64, Math.floor(img.height * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) return resolve(0);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      const { data, width, height } = ctx.getImageData(
        0,
        0,
        canvas.width,
        canvas.height,
      );
      // Convert to grayscale + apply 3x3 Laplacian and compute variance
      const gray = new Float32Array(width * height);
      for (let i = 0; i < gray.length; i++) {
        const r = data[i * 4];
        const g = data[i * 4 + 1];
        const b = data[i * 4 + 2];
        gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
      }

      let sum = 0;
      let sumSq = 0;
      let count = 0;
      for (let y = 1; y < height - 1; y++) {
        for (let x = 1; x < width - 1; x++) {
          const i = y * width + x;
          // Standard Laplacian kernel
          const lap =
            -gray[i - width] -
            gray[i - 1] +
            4 * gray[i] -
            gray[i + 1] -
            gray[i + width];
          sum += lap;
          sumSq += lap * lap;
          count++;
        }
      }
      const mean = sum / count;
      const variance = sumSq / count - mean * mean;
      resolve(variance);
    };
    img.onerror = () => resolve(0);
    img.src = dataUrl;
  });
}

export function WebcamCapture({
  onCapture,
  value = null,
  preview = null,
  aspect = '4:3',
  showOverlay = false,
  label = 'Capture',
  placeholder,
  facing = 'user',
  minSharpness = 25,
}: Props) {
  const webcamRef = useRef<Webcam>(null);
  // Treat `value` and `preview` as the same thing.
  const externalValue = value ?? preview ?? null;
  const [snapshot, setSnapshot] = useState<string | null>(externalValue);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sharpness, setSharpness] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Keep internal state in sync if the parent clears `value`
  useEffect(() => {
    if (externalValue !== snapshot) {
      setSnapshot(externalValue);
      setSharpness(null);
    }
  }, [externalValue]);

  const aspectClass =
    aspect === '16:9'
      ? 'aspect-video'
      : aspect === 'square'
        ? 'aspect-square'
        : 'aspect-[4/3]';

  const capture = useCallback(async () => {
    setError(null);
    const img = webcamRef.current?.getScreenshot();
    if (!img) {
      setError('Camera did not return a frame. Try again.');
      return;
    }
    setSnapshot(img);
    setAnalyzing(true);
    const sharp = await estimateSharpness(img);
    setSharpness(sharp);
    setAnalyzing(false);

    if (sharp < minSharpness) {
      setError(
        `Image looks blurry (sharpness ${Math.round(sharp)} < ${minSharpness}). Hold steady, ensure good lighting, and retake.`,
      );
      // Don't auto-accept — user must retake or force-accept
      return;
    }
    onCapture(img);
  }, [onCapture, minSharpness]);

  const retake = useCallback(() => {
    setSnapshot(null);
    setError(null);
    setSharpness(null);
    onCapture(null);
  }, [onCapture]);

  const forceAccept = useCallback(() => {
    if (snapshot) {
      onCapture(snapshot);
      setError(null);
    }
  }, [snapshot, onCapture]);

  return (
    <div className="w-full">
      {placeholder && (
        <p className="mb-2 text-xs text-bone-500">{placeholder}</p>
      )}
      <div
        className={cn(
          'relative overflow-hidden rounded-lg border border-ink-600 bg-ink-900',
          aspectClass,
        )}
      >
        {snapshot ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={snapshot}
            alt="Captured"
            className="h-full w-full object-cover"
          />
        ) : (
          <>
            <Webcam
              ref={webcamRef}
              audio={false}
              screenshotFormat="image/jpeg"
              screenshotQuality={0.92}
              videoConstraints={{
                facingMode: facing,
                width: 1280,
                height: 720,
              }}
              onUserMedia={() => setReady(true)}
              onUserMediaError={(e) =>
                setError(
                  typeof e === 'string'
                    ? e
                    : 'Cannot access camera. Check browser permissions.',
                )
              }
              className="h-full w-full object-cover"
            />
            {!ready && (
              <div className="absolute inset-0 grid place-items-center bg-ink-900/80 text-bone-500">
                <div className="size-8 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
              </div>
            )}
          </>
        )}

        {/* Overlay: scanning frame */}
        {showOverlay && !snapshot && (
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute inset-[15%] rounded-md border-2 border-amber/60">
              <span className="absolute -left-px -top-px size-3 border-l-2 border-t-2 border-amber" />
              <span className="absolute -right-px -top-px size-3 border-r-2 border-t-2 border-amber" />
              <span className="absolute -bottom-px -left-px size-3 border-b-2 border-l-2 border-amber" />
              <span className="absolute -bottom-px -right-px size-3 border-b-2 border-r-2 border-amber" />
            </div>
          </div>
        )}

        {/* Sharpness indicator after capture */}
        {snapshot && sharpness !== null && (
          <div
            className={cn(
              'absolute bottom-2 right-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider backdrop-blur-md',
              sharpness >= minSharpness
                ? 'bg-granted/20 text-granted'
                : 'bg-denied/20 text-denied',
            )}
          >
            {sharpness >= minSharpness ? (
              <CheckCircle2 className="size-3" />
            ) : (
              <AlertTriangle className="size-3" />
            )}
            sharpness {Math.round(sharpness)}
          </div>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-start gap-2 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-xs text-denied">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="mt-3 flex gap-2">
        {snapshot ? (
          <>
            <Button onClick={retake} variant="ghost" className="flex-1">
              <RotateCcw className="size-4" /> Retake
            </Button>
            {error && (
              <Button onClick={forceAccept} variant="ghost">
                Use anyway
              </Button>
            )}
            {!error && sharpness !== null && (
              <Button variant="primary" className="flex-1" disabled>
                <Check className="size-4" /> Captured
              </Button>
            )}
          </>
        ) : (
          <Button
            onClick={capture}
            disabled={!ready || analyzing}
            loading={analyzing}
            className="flex-1"
            size="lg"
          >
            <Camera className="size-4" /> {label}
          </Button>
        )}
      </div>
    </div>
  );
}
