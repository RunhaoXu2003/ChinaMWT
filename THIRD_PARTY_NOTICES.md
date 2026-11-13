# Component provenance and terms

The maintainers selected **Apache-2.0 for project-owned code** on13November2026. `LICENSE` applies to that code; it does not override independent component, model or data terms.

## MONAI / MedNeXt

- `vendor/mednext.py` and `vendor/mednext_block.py` derive from **MONAI1.5.2**.
- Original source copyright/Apache-2.0 notices remain in each file; the complete license is `vendor/MONAI_LICENSE.txt`.
- The MedNeXt block import points to the bundled sibling module. The architecture and parameter names were retained for the supplied checkpoint.

## Study and author-supplied components

- `vendor/study_engine.py`: selected functions/constants from `LVWT_Extraction_Batch-20260502_0824.py`; the original study source hash is `06b95c224457a38d2a0fa560f3a2ebedfcbad21eff61ff0818a19ea03bd998ec`.
- `core/segmentation.py` and `vendor/corseg_postprocessing.py`: the supplied CorSeg-CineSAX preprocessing/inference and selected post-processing functions. Source publication: <https://doi.org/10.64898/2026.04.01.26349955> (preprint).
- `vendor/jade_coordinates.py`: the author-supplied JADE coordinate-adaptation helpers used for legacy/v2 JSON conventions. This is not the complete JADE application; attribution is retained in the file.
- `reference/reference_model.json`: exported, frozen population reference coefficients and aggregated support counts from this project. It contains no individual training records.
- `assets/openscience.mplstyle`: plotting parameters adapted from the Open Science publication style used in the application.

## Runtime dependencies

PyQt6, Qt, PyTorch, NumPy, SciPy, nibabel, scikit-image, pydicom, Matplotlib and Pillow retain their own licenses. This source directory does not distribute their installed wheels or an executable runtime. PyQt/Qt distribution terms apply independently of the license on project-owned source.

## Separate checkpoint and data

`Multi-20260908.pth` is not included. Its provenance, checksum and separate availability requirements are described in `weights/README.md`. No patient image, mask or participant-level dataset is licensed or distributed by this code package.
