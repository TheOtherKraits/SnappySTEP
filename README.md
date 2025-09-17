# SnappySTEP
 Tool to read STEP files and generate STLs and dictionaries for meshing with SnappyHexMesh in OpenFOAM

# Current Status
This tool is under active development

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

# Features
* Import geometry from STEP assembly files.
* Generate STL files for snappHexMesh.
* Generate snappyHexMeshDict file.
* Detect interfaces between volumes for multi-region cases.
* Apply boundary patches, defined by coincident surface bodies.
* Detect baffles and create createBaffleDict files, defined by surface bodies embedded in solids solid bodies.
