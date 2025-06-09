from snappy_step.readerFuncs import *

# write_block_mesh_dict([-1.1,-1.1,-1.1,1.1,1.1,1.1],0.25,0.25,0.25)
write_snappy_step_dict_template()
old_sHMD = initialize_sHMD()
write_sHMD_Geo("testGeo", ["region1", "region2a", "regionC"]);
write_sHMD_Geo("testGeoInterface", [])
