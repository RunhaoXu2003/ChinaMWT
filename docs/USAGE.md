# Input, review and output guide

## Basic workflow

1. Choose **Files** or **Folder**, or drop files onto the window. Load one person's short-axis series at a time.
2. Review the file/slice/frame counts and the **Input list**. Resolve any ambiguous organization explicitly.
3. Enter the reference-model sex, age in years, height in centimeters and weight in kilograms.
4. For automatic segmentation, select the compatible separately supplied checkpoint and device. Alternatively, choose an existing ROI directory and use **Measure current ROI**.
5. Review the selected ED frame, analyzable slice coverage, contours and physical scale. The selected slice maximum is not necessarily patient MWT.
6. Save the project/report. Move the whole run directory when transferring a saved project; its JSON file alone is insufficient.

The Chinese/English choices at the top right update the interface in place. Analysis values and canonical JSON/CSV keys are independent of display language.

## NIfTI

- 2D/3D/4D images are interpreted as H/W/Z(/T); every plane is retained.
- Multiple files can use affines, time units/offsets and supported filename/JSON timing to form a slice/frame grid.
- Study-style `CineSAX-slice_frame_name` and `sliceN_frameN` identifiers are retained.
- ROI names begin with `ROI-` before the corresponding image filename. Labels are 0/background, 1/LV myocardium, 2/LV cavity and 3/RV.
- Image and mask shape/affine must match. The loader does not guess a transpose or register incompatible geometry.
- Declared meters/microns are converted to millimeters. Unknown NIfTI spatial units follow the study zoom-as-mm convention with an explicit flag; verify the physical scale before use.

## DICOM

Supported inputs include conventional single-frame MR, enhanced multiframe MR and legacy same-position cine with usable timing. Geometry uses physical position, orientation and pixel spacing; enhanced data use shared/per-frame metadata and rescaling. Compatible series may be grouped; conflicting patient/study/frame-of-reference, echo/component or duplicate-instance metadata are rejected.

Uncompressed and RLE-enhanced MR are covered by synthetic tests. Other compression requires an available pydicom decoder. Broad scanner/vendor acceptance has not been established.

## Ambiguous or incomplete input

When metadata cannot distinguish repeated volumes, new slices and new phases, choose the appropriate policy: within-position order, file slice blocks or file time blocks. The choice is saved in `input_manifest.json`. Missing grid cells remain missing; images are not silently padded or interpolated. Import original DICOM and converted NIfTI as separate groups.

## Saved output

Each run has a separate directory containing normalized images, chosen masks, `analysis.json`, `slice_measurements.csv`, `input_manifest.json`, `project.lvwt.json`, `report.html` and a review image. Segmentation-only runs retain successful masks when no valid MWT can be calculated. A cancelled/failed run may retain partial output; inspect its recorded status.

Original input files are read-only, and an output directory cannot be placed inside an input directory. Saved outputs can contain image-derived data and local source paths and must not be uploaded as part of this source repository.
