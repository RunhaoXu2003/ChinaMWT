# Measurement and frozen reference definitions

The scientific implementation follows the study's2026-05-02measurement functions and frozen sex-specific R reference models.

## MWT

The longest consecutive eligible short-axis slice block is used. Automatic end-diastole is the frame with the greatest summed LV-cavity mask area. Endocardial/epicardial boundaries undergo the study smoothing and polar correspondence procedure;72points are sampled uniformly along midline arc length. Distances use physical in-plane spacing. Patient MWT is the maximum across available analyzable end-diastolic slices. This is not a separately implemented strict wall-normal intersection solver.

`Slice max` is the selected plane's value and may differ from patient MWT. AHA location is not assigned with fewer than four valid ED slices. The raw maximum is retained, while study-rounded MWT is used for the reference calculation.

## Reference model

```text
BSA = 0.007184 × height_cm^0.725 × weight_kg^0.425
μ = frozen sex-specific population prediction(age, BSA)
UL = μ + q97.5,sex × σsex
Z = (study-rounded MWT − μ) / σsex
above_limit = MWT >= UL
```

The exported representation uses additive natural cubic splines and linear boundary extrapolation. Center-specific random effects are not added. The empirical multipliers are not replaced with1.96,2or an assumed standard-normal percentile. `reference_model.json` preserves the frozen values without refitting.

Support flags report marginal extrapolation, BMI eligibility and sparse age/BSA support cells. They do not certify that every joint demographic combination is well represented. UL indicates departure from a population reference; Z is not a probability of HCM.
