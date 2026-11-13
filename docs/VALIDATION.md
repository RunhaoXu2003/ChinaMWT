# Verification scope

## Included reproducible checks

- 778 deterministic R prediction queries spanning lookup points, seeded random inputs and boundaries/extrapolation; tolerance 1e-9.
- Known-value synthetic NIfTI/DICOM import tests, including enhanced per-frame geometry, timing and rescaling.
- Qt startup and Chinese/English language switching without private images or weights.

The exported query CSV contains hypothetical test inputs and calculated outputs, not individual participant records. The lookup CSV contains aggregate model predictions. Synthetic image fixtures are generated when tests run and are excluded from source uploads.

## Existing study/workbench evidence

Local development also checked selected real-image inference parity, same-mask extraction replay and project export. Same-mask replay agreed with the original study script in one healthy and one HCM case. These private fixtures are not distributed, and the public tests do not claim to repeat them.

One healthy-case historical aggregate differed from current-mask replay (7.94 versus 7.59 mm). In the separate manuscript example, archived masks reproduced 9.07 mm while the current automatic path gave 5.89 mm. These are distinct version/provenance observations, not substituted cohort results. They remain disclosed in the study's supplemental methods.

The local checks do not establish whole-cohort replay, scan–rescan reproducibility, scanner/vendor-wide DICOM acceptance, clinical diagnostic accuracy, clinical workflow benefit or interchangeability of segmentation versions. Clinical evaluation integrates morphology, history, genetics and alternative causes of hypertrophy; the software's reference exceedance alone is not a diagnosis.
