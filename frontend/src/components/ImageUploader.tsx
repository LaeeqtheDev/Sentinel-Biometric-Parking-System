'use client';

import { ChangeEvent, DragEvent, useRef, useState } from 'react';
import { Upload, X, ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

interface Props {
  onSelect: (file: File, dataUrl: string) => void;
  onClear?: () => void;
  preview?: string | null;
  label?: string;
}

export function ImageUploader({
  onSelect,
  onClear,
  preview,
  label = 'Upload an image',
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [internalPreview, setInternalPreview] = useState<string | null>(
    preview ?? null,
  );

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setInternalPreview(dataUrl);
      onSelect(file, dataUrl);
    };
    reader.readAsDataURL(file);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const clear = () => {
    setInternalPreview(null);
    if (inputRef.current) inputRef.current.value = '';
    onClear?.();
  };

  const shown = internalPreview ?? preview;

  return (
    <div className="w-full">
      {shown ? (
        <div className="relative overflow-hidden rounded-lg border border-ink-600 bg-ink-900">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={shown} alt="Preview" className="aspect-[4/3] w-full object-cover" />
          <button
            type="button"
            onClick={clear}
            className="absolute right-2 top-2 grid size-8 place-items-center rounded-full border border-ink-600 bg-ink-900/80 text-bone-300 backdrop-blur transition-colors hover:border-denied hover:text-denied"
            aria-label="Remove"
          >
            <X className="size-4" />
          </button>
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            'group flex aspect-[4/3] cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed transition-colors',
            dragActive
              ? 'border-amber bg-amber/5'
              : 'border-ink-600 bg-ink-900/40 hover:border-ink-500 hover:bg-ink-800/40',
          )}
        >
          <div
            className={cn(
              'grid size-12 place-items-center rounded-full border transition-colors',
              dragActive
                ? 'border-amber bg-amber/10 text-amber'
                : 'border-ink-600 text-bone-400 group-hover:border-ink-500',
            )}
          >
            <Upload className="size-5" />
          </div>
          <div className="text-center">
            <p className="text-sm text-bone-200">{label}</p>
            <p className="mt-0.5 text-xs text-bone-500">
              Drag & drop or click to browse
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={onChange}
          />
        </div>
      )}
    </div>
  );
}
