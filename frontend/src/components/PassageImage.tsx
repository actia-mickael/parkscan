import { useEffect, useState } from "react";

import { passagesApi } from "@/api/endpoints";

export default function PassageImage({
  passageId,
  kind,
  className = "",
  alt,
}: {
  passageId: string;
  kind: "full" | "plate" | "vehicle";
  className?: string;
  alt?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setUrl(null);
    setFailed(false);
    passagesApi
      .image(passageId, kind)
      .then((res) => {
        if (!cancelled) setUrl(res.data.url);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [passageId, kind]);

  if (failed) return <div className={`flex items-center justify-center bg-slate-800 text-xs text-slate-500 ${className}`}>pas d'image</div>;
  if (!url) return <div className={`animate-pulse bg-slate-800 ${className}`} />;
  return <img src={url} alt={alt ?? kind} className={`object-cover ${className}`} onError={() => setFailed(true)} />;
}
