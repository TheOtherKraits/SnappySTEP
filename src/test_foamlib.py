from snappy_step.readerFuncs import *

# write_block_mesh_dict([-1.1,-1.1,-1.1,1.1,1.1,1.1],0.25,0.25,0.25)
write_snappy_step_dict_template()
old_sHMD , new_sHMD = initialize_sHMD()
write_sHMD_Geo(new_sHMD, "testGeo", ["region1", "region2a", "regionC"]);
write_sHMD_Geo(new_sHMD, "testGeoInterface", [])
write_sHMD_refinement_surfaces(new_sHMD,"testRefinementSurf",["regionA", "regionB"],old_sHMD,[2,2])
write_sHMD_refinement_surfaces(new_sHMD,"testRefinementSurf2",[],old_sHMD,[2,2])

# write_sHMD_refinement_surfaces_cellZone(new_sHMD,)


write_sHMD(new_sHMD)
