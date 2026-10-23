import { useState } from "react";
import type { SyntheticEvent } from "react";

import { usePresignedImage } from "@/components/PassageImage";
import { percent } from "@/lib/format";
import type { PassageRead } from "@/types/api";

// Image complète d'une capture avec, par-dessus, les zones détectées par le service ML :
// le véhicule (vert si autorisé, rouge si refusé) et la plaque (bleu) avec le texte lu.
// Les cadres sont en pixels de l'image d'origine ; on les convertit en pourcentages une fois
// l'image chargée, pour qu'ils suivent le redimensionnement.

interface Box {
  left: string;
  top: string;
  width: string;
  height: string;
}

function toBox(bbox: number[] | null, width: number, height: number): Box | null {
  if (!bbox || bbox.length !== 4 || width <= 0 || height <= 0) return null;
  const [x1, y1, x2, y2] = bbox;
  return {
    left: `${(100 * x1) / width}%`,
    top: `${(100 * y1) / height}%`,
    width: `${(100 * (x2 - x1)) / width}%`,
    height: `${(100 * (y2 - y1)) / height}%`,
  };
}

export default function CaptureFrame({
  passage,
  showBoxes = true,
  className = "rounded-lg",
}: {
  passage: PassageRead;
  showBoxes?: boolean;
  className?: string;
}) {
  const { url, failed } = usePresignedImage(passage.id, "full");
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [broken, setBroken] = useState(false);

  if (!passage.image_key || failed || broken) {
    return (
      <div className={`flex aspect-video items-center justify-center bg-slate-800 text-xs text-slate-500 ${className}`}>
        pas d'image
      </div>
    );
  }
  if (!url) return <div className={`aspect-video animate-pulse bg-slate-800 ${className}`} />;

  const vehicle = size ? toBox(passage.vehicle_bbox, size.width, size.height) : null;
  const plate = size ? toBox(passage.plate_bbox, size.width, size.height) : null;
  const vehicleColor = passage.decision === "allowed" ? "border-emerald-400/80" : "border-red-400/80";
  // Étiquette ancrée à droite quand la plaque est dans la moitié droite, pour ne pas sortir du cadre
  const plateOnRight = size && passage.plate_bbox ? passage.plate_bbox[0] > size.width / 2 : false;

  return (
    <div className={`relative overflow-hidden bg-slate-950 ${className}`}>
      <img
        src={url}
        alt={`capture ${passage.plate_text ?? "sans plaque"}`}
        className="block h-auto w-full"
        onLoad={(event: SyntheticEvent<HTMLImageElement>) =>
          setSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
        }
        onError={() => setBroken(true)}
      />
      {showBoxes && vehicle && <div className={`pointer-events-none absolute rounded border-2 ${vehicleColor}`} style={vehicle} />}
      {showBoxes && plate && (
        <div className="pointer-events-none absolute border-2 border-sky-300" style={plate}>
          <span className={`absolute -top-6 whitespace-nowrap rounded bg-sky-300 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-950 ${plateOnRight ? "right-0" : "left-0"}`}>
            {passage.plate_text ?? "?"} · {percent(passage.ocr_conf)}
          </span>
        </div>
      )}
    </div>
  );
}
