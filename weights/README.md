# Optional segmentation checkpoint

Automatic inference expects `Multi-20260908.pth` in this directory by default. You may instead choose a checkpoint path in the interface. The application can calculate thickness from existing ROI masks and evaluate demographic references without this checkpoint.

- Architecture: MedNeXt-L,2D, kernel5, one image channel, four output classes,224×224input.
- Expected size: **741045497bytes**.
- SHA-256: **`1c9f84c58817dd802c712b69b07ae4f174b3cce1f07be11f8a3d93e6e7862c33`**.
- Labels:0background,1LV myocardium,2LV cavity,3RV.

The checkpoint is supplied separately by the maintainers; no public model-download URL or model-specific redistribution license is asserted here. Contact the project maintainers through the repository for availability. Once distribution terms are settled, this741MB file belongs in an appropriate large-file/model host or GitHub Release asset, not an ordinary Git source commit.

Replacing the checkpoint can change segmentation and measured MWT. Reference-computation agreement alone does not establish clinical equivalence of different segmentation paths.
