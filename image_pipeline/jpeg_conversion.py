"""Conversion de dossiers de TIFF en JPEG.

Chaque fichier .tif / .tiff du dossier source (sous-dossiers compris) donne un
JPEG au même emplacement relatif dans le dossier de destination. Les couleurs
sont converties en sRGB lorsque le TIFF porte un profil ICC, la résolution
(dpi) est conservée et un profil sRGB est intégré au JPEG. Un TIFF de
plusieurs pages donne un JPEG par page (nom-1.jpg, nom-2.jpg, …).

Les originaux ne sont jamais modifiés et un JPEG déjà présent n'est jamais
écrasé.

Utilisation :
    python -m image_pipeline.jpeg_conversion DOSSIER_TIFF DOSSIER_JPEG [--qualite 95]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from .io_utils import _convert_frame_to_srgb

TIFF_EXTENSIONS = {".tif", ".tiff"}
DEFAULT_QUALITY = 95
_SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _to_8_bits(frame: Image.Image) -> Image.Image:
    """Ramène une image 16 ou 32 bits en niveaux de gris sur 8 bits."""

    if frame.mode in {"I;16", "I;16B", "I;16L", "I;16N"}:
        values = np.asarray(frame, dtype=np.uint16)
        return Image.fromarray((values >> 8).astype(np.uint8), mode="L")
    if frame.mode in {"I", "F"}:
        values = np.asarray(frame, dtype=np.float64)
        top = float(values.max()) if values.size else 0.0
        scale = 255.0 / top if top > 255.0 else 1.0
        return Image.fromarray(np.clip(values * scale, 0, 255).astype(np.uint8), mode="L")
    return frame


def _flatten(image: Image.Image) -> Image.Image:
    """JPEG n'a pas de transparence : les zones transparentes deviennent blanches."""

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def _jpeg_frames(source: Path) -> list[tuple[Image.Image, tuple[float, float] | None]]:
    """Lit toutes les pages d'un TIFF, prêtes à être enregistrées en JPEG."""

    frames: list[tuple[Image.Image, tuple[float, float] | None]] = []
    with Image.open(source) as image:
        for index in range(int(getattr(image, "n_frames", 1))):
            image.seek(index)
            info = dict(image.info)
            dpi_value = info.get("dpi")
            dpi = None
            if isinstance(dpi_value, tuple) and len(dpi_value) >= 2 and dpi_value[0] > 0:
                dpi = (float(dpi_value[0]), float(dpi_value[1]))
            frame = ImageOps.exif_transpose(image.copy())
            frame = _to_8_bits(frame)
            rendered = _convert_frame_to_srgb(frame, info.get("icc_profile"))
            frames.append((_flatten(rendered), dpi))
    return frames


def convert_folder(
    source_dir: Path,
    target_dir: Path,
    *,
    quality: int = DEFAULT_QUALITY,
    log=print,
) -> dict[str, int]:
    """Convertit tous les TIFF de ``source_dir`` en JPEG dans ``target_dir``."""

    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    totals = {"tiff_trouves": 0, "jpeg_crees": 0, "deja_presents": 0, "erreurs": 0}
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Dossier introuvable : {source_dir}")

    sources = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in TIFF_EXTENSIONS
        ),
        key=lambda path: str(path).casefold(),
    )
    totals["tiff_trouves"] = len(sources)
    if not sources:
        log(f"Aucun fichier TIFF dans {source_dir}.")
        return totals

    for number, source in enumerate(sources, start=1):
        relative = source.relative_to(source_dir)
        log(f"[{number}/{len(sources)}] {relative}")
        try:
            frames = _jpeg_frames(source)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            totals["erreurs"] += 1
            log(f"  ERREUR : fichier illisible ({exc}).")
            continue

        for page, (image, dpi) in enumerate(frames, start=1):
            stem = relative.stem if len(frames) == 1 else f"{relative.stem}-{page}"
            target = target_dir / relative.parent / f"{stem}.jpg"
            if target.exists():
                totals["deja_presents"] += 1
                log(f"  {target.name} existe déjà : conservé tel quel.")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            options: dict[str, object] = {
                "quality": quality,
                "subsampling": 0,  # 4:4:4 : pas de perte de finesse des couleurs
                # Pas d'option « optimize » : avec une image de la taille d'un
                # scan, elle fait échouer l'écriture (« Suspension not allowed »).
                "icc_profile": _SRGB_PROFILE,
            }
            if dpi is not None:
                options["dpi"] = dpi
            temporary = target.with_name(f".{target.name}.tmp")
            try:
                image.save(temporary, format="JPEG", **options)
                temporary.replace(target)
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                totals["erreurs"] += 1
                log(f"  ERREUR : impossible d'écrire {target.name} ({exc}).")
                continue
            totals["jpeg_crees"] += 1
            log(f"  -> {target.relative_to(target_dir)}")

    log(
        "Terminé : "
        f"{totals['jpeg_crees']} JPEG créé(s), "
        f"{totals['deja_presents']} déjà présent(s), "
        f"{totals['erreurs']} erreur(s)."
    )
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m image_pipeline.jpeg_conversion",
        description="Convertit des dossiers de fichiers TIFF en JPEG.",
    )
    parser.add_argument("source", type=Path, help="dossier contenant les TIFF")
    parser.add_argument("destination", type=Path, help="dossier où créer les JPEG")
    parser.add_argument(
        "--qualite",
        type=int,
        default=DEFAULT_QUALITY,
        help=f"qualité JPEG de 1 à 100 (défaut : {DEFAULT_QUALITY})",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.qualite <= 100:
        parser.error("la qualité doit être comprise entre 1 et 100")
    try:
        totals = convert_folder(args.source, args.destination, quality=args.qualite)
    except (OSError, ValueError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    return 1 if totals["erreurs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
