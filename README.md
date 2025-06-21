# SnappySTEP
 Tool to read STEP files and generate STLs and dictionaries for meshing with SnappyHexMesh in OpenFOAM

# Basic Usage

1. Build OpenFOAM Case directory and required dictionaries (e.g. `system/controlDict`)
2. Place Step file in `constant/geometry/` directory.
3. Run `snappyStepConfig` to generate base `system/snappyStepDict` file
4. Make any edits to `snappyStepDict`
5. Run `snappyStep`
4. Run `blockMesh`
5. Run `snappyHexMesh -overwrite`
6. If multi-region case, run `./snappyStepSplitMeshRegions`
7. Run `checkMesh`
8. Inspect mesh in ParaView