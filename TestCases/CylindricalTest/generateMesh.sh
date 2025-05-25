snappyHexMeshConfig -explicitFeatures -cylindricalBackground
blockMesh
./snappyStep.sh
snappyHexMesh -overwrite
./snappyStepSplitMeshRegions.sh
checkMesh