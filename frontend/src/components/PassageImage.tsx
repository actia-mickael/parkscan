import { useEffect, useState } from "react";

import { passagesApi } from "@/api/endpoints";

export type ImageKind = "full" | "plate" | "vehicle";

interface CachedUrl {
  url: string;
  expiresAt: number;
}

// Cache des URLs présignées : le direct rafraîchit la liste toutes les 3 s, inutile de redemander
// une URL encore valable. Marge de sécurité avant l'expiration réelle.
const cache = new Map<string, CachedUrl>();
const inflight = new Map<string, Promise<string>>();
const SAFETY_MARGIN_MS = 30_000;

export function presignedImageUrl(passageId: string, kind: ImageKind): Promise<string> {
  const key = `${passageId}:${kind}`;
  const hit = cache.get(key);
  if (hit && hit.expiresAt > Date.now()) return Promise.resolve(hit.url);
  const pending = inflight.get(key);
  if (pending) return pending;
  const request = passagesApi
    .image(passageId, kind)
    .then((res) => {
      cache.set(key, { url: res.data.url, expiresAt: Date.now() + res.data.expires_in * 1000 - SAFETY_MARGIN_MS });
      return res.data.url;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, request);
  return request;
}

export function usePresignedImage(passageId: string, kind: ImageKind, available = true): { url: string | null; failed: boolean } {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setUrl(null);
    setFailed(!available);
    if (!available) return undefined; // image supprimée (rétention) ou jamais produite : pas d'appel
    presignedImageUrl(passageId, kind)
      .then((value) => {
        if (!cancelled) setUrl(value);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [passageId, kind, available]);

  return { url, failed };
}

export default function PassageImage({
  passageId,
  kind,
  className = "",
  alt,
  fit = "cover",
  available = true,
}: {
  passageId: string;
  kind: ImageKind;
  className?: string;
  alt?: string;
  fit?: "cover" | "contain";
  available?: boolean;
}) {
  const { url, failed } = usePresignedImage(passageId, kind, available);
  const [broken, setBroken] = useState(false);

  useEffect(() => {
    setBroken(false);
  }, [passageId, kind]);

  if (failed || broken) {
    return <div className={`flex items-center justify-center bg-slate-800 text-xs text-slate-500 ${className}`}>pas d'image</div>;
  }
  if (!url) return <div className={`animate-pulse bg-slate-800 ${className}`} />;
  return (
    <img
      src={url}
      alt={alt ?? kind}
      className={`${fit === "contain" ? "object-contain" : "object-cover"} ${className}`}
      onError={() => setBroken(true)}
    />
  );
}
