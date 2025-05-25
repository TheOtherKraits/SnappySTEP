snappyHexMeshConfig -explicitFeatures
blockMesh
./snappyStep.sh 
snappyHexMesh -overwrite
./snappyStepSplitMeshRegions.sh
checkMesh