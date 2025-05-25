snappyHexMeshConfig -explicitFeatures
blockMesh
./snappyStep.sh
surfaceFeatures
snappyHexMesh -overwrite
./snappyStepSplitMeshRegions.sh
checkMesh