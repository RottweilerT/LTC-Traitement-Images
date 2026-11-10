from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

from image_pipeline.jpeg_conversion import convert_folder, main


def _silent(_: str) -> None:
    pass


class JpegConversionTests(unittest.TestCase):
    def _tree(self, root: Path) -> tuple[Path, Path]:
        source = root / "TIF_A_CONVERTIR"
        target = root / "JPEG_CONVERTIS"
        (source / "Lot_001").mkdir(parents=True)
        (source / "Lot_002").mkdir(parents=True)
        return source, target

    def test_folders_are_mirrored_and_colours_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            rgb = np.zeros((40, 60, 3), dtype=np.uint8)
            rgb[:, :30] = (200, 40, 60)
            rgb[:, 30:] = (5, 0, 2)
            srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            Image.fromarray(rgb).save(
                source / "Lot_001" / "168875.tif", dpi=(600, 600), icc_profile=srgb,
                compression="tiff_lzw",
            )
            Image.fromarray(rgb).save(source / "Lot_002" / "169262.TIFF", dpi=(300, 300))
            (source / "Lot_001" / "notes.txt").write_text("à ignorer", encoding="utf-8")

            totals = convert_folder(source, target, log=_silent)

            self.assertEqual(totals["tiff_trouves"], 2)
            self.assertEqual(totals["jpeg_crees"], 2)
            first = target / "Lot_001" / "168875.jpg"
            second = target / "Lot_002" / "169262.jpg"
            self.assertTrue(first.is_file() and second.is_file())
            with Image.open(first) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, (60, 40))
                self.assertEqual(tuple(round(v) for v in image.info["dpi"]), (600, 600))
                self.assertIn("icc_profile", image.info)
                pixels = np.asarray(image).astype(int)
            # Qualité 100 en 4:4:4 : couleurs fidèles à quelques niveaux près.
            self.assertLess(np.abs(pixels[20, 10] - (200, 40, 60)).max(), 6)
            self.assertLess(np.abs(pixels[20, 50] - (5, 0, 2)).max(), 6)
            self.assertFalse((target / "Lot_001" / "notes.jpg").exists())

    def test_transparency_becomes_white(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            rgba = np.zeros((10, 10, 4), dtype=np.uint8)
            rgba[..., :3] = (10, 120, 30)
            rgba[:5, :, 3] = 255  # moitié haute opaque, moitié basse transparente
            Image.fromarray(rgba, mode="RGBA").save(source / "Lot_001" / "a.tif")

            convert_folder(source, target, log=_silent)

            with Image.open(target / "Lot_001" / "a.jpg") as image:
                pixels = np.asarray(image).astype(int)
            self.assertLess(np.abs(pixels[2, 5] - (10, 120, 30)).max(), 8)
            self.assertGreater(pixels[8, 5].min(), 245)

    def test_multipage_tiff_gives_one_jpeg_per_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            pages = [Image.new("RGB", (8, 8), colour) for colour in ("red", "green", "blue")]
            pages[0].save(source / "Lot_001" / "planche.tif", save_all=True, append_images=pages[1:])

            totals = convert_folder(source, target, log=_silent)

            self.assertEqual(totals["jpeg_crees"], 3)
            names = sorted(path.name for path in (target / "Lot_001").iterdir())
            self.assertEqual(names, ["planche-1.jpg", "planche-2.jpg", "planche-3.jpg"])

    def test_16_bit_greyscale_is_converted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            values = np.full((6, 6), 40000, dtype=np.uint16)
            Image.fromarray(values, mode="I;16").save(source / "Lot_001" / "gris16.tif")

            convert_folder(source, target, log=_silent)

            with Image.open(target / "Lot_001" / "gris16.jpg") as image:
                pixel = np.asarray(image.convert("L"))[3, 3]
            self.assertAlmostEqual(int(pixel), 40000 >> 8, delta=3)

    def test_existing_jpeg_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            Image.new("RGB", (8, 8), "red").save(source / "Lot_001" / "x.tif")
            existing = target / "Lot_001" / "x.jpg"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"RETOUCHE-A-CONSERVER")

            totals = convert_folder(source, target, log=_silent)

            self.assertEqual(existing.read_bytes(), b"RETOUCHE-A-CONSERVER")
            self.assertEqual(totals["deja_presents"], 1)
            self.assertEqual(totals["jpeg_crees"], 0)

    def test_original_tiff_is_untouched_and_bad_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            good = source / "Lot_001" / "bon.tif"
            Image.new("RGB", (8, 8), "blue").save(good)
            before = good.read_bytes()
            (source / "Lot_001" / "abime.tif").write_bytes(b"pas une image")

            totals = convert_folder(source, target, log=_silent)

            self.assertEqual(good.read_bytes(), before)
            self.assertEqual(totals["jpeg_crees"], 1)
            self.assertEqual(totals["erreurs"], 1)
            exit_code = main([str(source), str(Path(directory) / "autre")])
            self.assertEqual(exit_code, 1)

    def test_scan_sized_image_is_written(self) -> None:
        """Régression : une image de la taille d'un vrai scan doit s'écrire."""

        with tempfile.TemporaryDirectory() as directory:
            source, target = self._tree(Path(directory))
            noise = (np.random.default_rng(0).random((3424, 2464, 3)) * 255).astype(np.uint8)
            Image.fromarray(noise).save(source / "Lot_001" / "168954.tif", dpi=(300, 300))

            totals = convert_folder(source, target, log=_silent)

            self.assertEqual(totals["erreurs"], 0)
            with Image.open(target / "Lot_001" / "168954.jpg") as image:
                self.assertEqual(image.size, (2464, 3424))


if __name__ == "__main__":
    unittest.main()
