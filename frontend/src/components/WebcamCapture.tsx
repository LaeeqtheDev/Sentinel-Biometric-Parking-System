'use client';

import { useCallback, useRef, useState } from 'react';
import Webcam from 'react-webcam';
import { Camera, RotateCcw, Check } from 'lucide-react';
import { Button } from './Button';
import { cn } from '@/lib/utils';

interface Props {
  onCapture: (imageDataUrl: string) => void;
  /** Aspect ratio: '4:3' | '16:9' | 'square' */
  aspect?: '4:3' | '16:9' | 'square';
  /** Show the scanning grid overlay (face-recognition look) */
  showOverlay?: boolean;
  label?: string;
  preview?: string | null;
}

export function WebcamCapture({
  onCapture,
  aspect = '4:3',
  showOverlay = false,
  label = 'Capture',
  preview,
}: Props) {
  const webcamRef = useRef<Webcam>(null);
  const [snapshot, setSnapshot] = useState<string | null>(preview || null);
  const [ready, setReady] = useState(false);

  const aspectClass =
    aspect === '16:9'
      ? 'aspect-video'
      : aspect === 'square'
        ? 'aspect-square'
        : 'aspect-[4/3]';

  const capture = useCallback(() => {
    const img = webcamRef.current?.getScreenshot();
    if (img) {
      setSnapshot(img);
      onCapture(img);
    }
  }, [onCapture]);

  const retake = useCallback(() => {
    setSnapshot(null);
  }, []);

  return (
    <div className="w-full">
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
          <Webcam
            ref={webcamRef}
            audio={false}
            screenshotFormat="image/jpeg"
            videoConstraints={{ facingMode: 'user' }}
            onUserMedia={() => setReady(true)}
            className="h-full w-full object-cover"
          />
        )}

        {/* Overlay: scanning frame */}
        {showOverlay && !snapshot && (
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute inset-[15%] rounded-md border-2 border-amber/60">
              {/* Corner brackets */}
              {[
                'top-0 left-0 border-l-2 border-t-2 rounded-tl-md',
                'top-0 right-0 border-r-2 border-t-2 rounded-tr-md',
                'bottom-0 left-0 border-l-2 border-b-2 rounded-bl-md',
                'bottom-0 right-0 border-r-2 border-b-2 rounded-br-md',
              ].map((cls, i) => (
                <span
                  key={i}
                  className={cn(
                    'absolute size-4 border-amber-glow',
                    cls.replace('rounded-md', ''),
                  )}
                />
              ))}
            </div>
            {/* Scanning line */}
            <div className="absolute inset-x-[15%] top-[15%] h-[70%] overflow-hidden">
              <div className="h-0.5 bg-gradient-to-r from-transparent via-amber-glow to-transparent animate-scan" />
            </div>
          </div>
        )}

        {/* Status pill */}
        {!snapshot && (
          <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full border border-ink-600 bg-ink-900/80 px-2 py-1 backdrop-blur">
            <span
              className={cn(
                'inline-block size-1.5 rounded-full',
                ready ? 'bg-granted animate-pulse-soft' : 'bg-pending',
              )}
            />
            <span className="font-mono text-[10px] uppercase tracking-wider text-bone-300">
              {ready ? 'LIVE' : 'Initializing'}
            </span>
          </div>
        )}
      </div>

      <div className="mt-3 flex justify-center gap-2">
        {snapshot ? (
          <>
            <Button variant="secondary" size="md" onClick={retake} type="button">
              <RotateCcw className="size-4" /> Retake
            </Button>
            <Button variant="primary" size="md" disabled type="button">
              <Check className="size-4" /> Captured
            </Button>
          </>
        ) : (
          <Button
            variant="primary"
            size="md"
            onClick={capture}
            disabled={!ready}
            type="button"
          >
            <Camera className="size-4" /> {label}
          </Button>
        )}
      </div>
    </div>
  );
}
