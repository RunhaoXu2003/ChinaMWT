# ChinaMWT

**LVWT CineSAX Workbench 0.3.0 — CMR segmentation, wall-thickness measurement and demographic reference interpretation.**

Project repository: <https://github.com/RunhaoXu2003/ChinaMWT>

ChinaMWT combines short-axis cine CMR image review, optional CorSeg segmentation, patient-level maximum wall thickness (MWT), and frozen reference limits derived in Chinese adults. The interface supports **English and 中文**.

## Features

- Load one or multiple NIfTI files, conventional MR DICOM series, or supported enhanced/multiframe MR DICOM files.
- Run automatic segmentation when the separately supplied compatible checkpoint is installed, or measure existing masks.
- Review end-diastole, layer coverage, contours, physical scale and the location of maximum thickness.
- Enter sex, age, height and weight to calculate body surface area, expected MWT, an individualized upper reference limit and a standardized Z score.
- Save masks, annotated views, measurement tables, provenance and a reopenable local project.

## Installation

Use Python **3.10** (the verified application environment used 3.10.20). Create a virtual environment and install the dependencies from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py --language en
```

On Linux/macOS, the virtual-environment executable is `.venv/bin/python`. These platforms have not undergone the Windows desktop acceptance checks. Select the official PyTorch build appropriate for your CUDA hardware or CPU; see <https://pytorch.org/get-started/locally/>. The supplied requirements record the tested package versions rather than bundling an interpreter or GPU runtime.

Alternative launch commands:

```text
python launch.py --check
python launch.py --language en
python launch.py --language zh
python launch.py --input "cine.nii.gz"
python launch.py --input "stack1.nii.gz" "stack2.nii.gz"
python launch.py --project "saved/project.lvwt.json"
```

`launch.py` checks the active Python, a repository-local virtual environment, and an optional `LVWT_PYTHON` setting. It does not depend on the developer's machine paths.

## Segmentation weights

Automatic segmentation requires the separately supplied **`Multi-20260908.pth`** checkpoint. See [weights/README.md](weights/README.md) for architecture, checksum and placement. **The checkpoint is not included in this source upload.** Existing-ROI measurement and the frozen reference calculator do not require it.

For existing masks, labels are 0/background, 1/LV myocardium, 2/LV cavity and 3/RV. Image and mask geometry must match. Details of input organization, measurement and saved outputs are in [docs/USAGE.md](docs/USAGE.md).

## Reference calculation

```python
from core.reference import ReferenceModel

model = ReferenceModel()
result = model.evaluate(
    mwt=10.0, sex="Female", age=50,
    height=165, weight=60,
)
print(result["upper_limit_mm"], result["z_score"], result["above_limit"])
```

The example above is a hypothetical query, not participant data. BSA follows the Du Bois formula. The frozen sex-specific population prediction is combined with the empirical upper-tail multiplier and residual SD. The application preserves the study's two-decimal measured-MWT convention; reference parameters are not rounded for classification. Z is a residual-standardized measurement, not an HCM probability. See [docs/METHODS.md](docs/METHODS.md).

## Reproducibility checks

```text
python tests/check_reference.py
python tools/validate_imports.py
python tests/check_ui_startup.py
```

- `check_reference.py` uses 778 deterministic exported R reference queries (lookup, seeded random and boundary/extrapolation inputs).
- `validate_imports.py` creates known-value **synthetic** NIfTI/DICOM fixtures locally. It does not require patient images or segmentation weights.
- `check_ui_startup.py` checks Qt startup and bilingual switching without running inference.

These are technical consistency checks. They are not additional clinical cases or independent clinical validation. Existing same-mask and model-version differences are summarized in [docs/VALIDATION.md](docs/VALIDATION.md).

## Data and distribution

The upload contains source code, exported reference coefficients, aggregated support counts, lookup values and deterministic test queries. It contains **no participant images, masks, participant-level clinical tables, private QA runs or local configuration**. R fitted-model objects are omitted because they can retain training data; the application uses the compact exported representation and does not need R at runtime.

Local projects, logs and reports can contain source paths or patient-derived information and are excluded by `.gitignore`.

## License and attribution

Project-owned code is licensed under the **Apache License, Version 2.0**; see [LICENSE](LICENSE). Third-party components retain their own notices and terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The software license does not automatically license segmentation checkpoints, patient data or third-party runtime packages.

## 中文简要说明

创建Python环境并安装依赖后，运行`python launch.py --language zh`。选择或拖入单病例短轴影像，输入人口学参数，运行自动分割或选择已有ROI测厚。自动分割权重需单独配置；已有ROI和正常参考计算可独立使用。请同时查看层面覆盖、分割轮廓和单位说明；显示层的最大厚度与整例MWT是不同读数。正常参考上限用于研究和临床解释的辅助，不能单独确诊HCM。
