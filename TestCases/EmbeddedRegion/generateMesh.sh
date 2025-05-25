snappyHexMeshConfig -implicitFeatures
blockMesh
./snappyStep.sh
snappyHexMesh -overwrite
./snappyStepSplitMeshRegions.sh
checkMesh