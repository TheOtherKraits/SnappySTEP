import argparse
from .geometry import *
from .read_write import *

def run_snappy_step(file_name,v,vf):
    """
    :param file_name: TODO
    :param v: TODO
    :v vf: TODO
    """
    # Determine if in openfoam case structure and if it is .org or .com version
    geometry_path = get_geometry_path()

    # Read Config
    config = read_config()
    validate_snappy_step_dict(config)
    
    # Find geometry files
    step_file = find_geometry_file(file_name, geometry_path)
    step_name = os.path.split(step_file)[-1].split('.')[0]

    # Begin gmsh operations
    gmsh.initialize()
    load_step_file(step_file, config)
    imprint_geometry()
    validate_gmsh_names()
    volumes, interfaces = process_geometry(config)
    default_volume = assign_cell_zones_to_interfaces(volumes)
    model_bounding_box = gmsh.model.get_bounding_box(-1,-1)

    # optionally view faces and volumes and exit before mesh
    if vf:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open. Close gmsh window to continue.")
        gmsh.fltk.run()
        ans = ask_yes_no("Would you like to continue?")
        gmsh.fltk.finalize()
        if not ans:
            gmsh.finalize()
            exit(1)

    # Generate Mesh
    generate_surface_mesh(config)

    # Write Mesh
    write_surface_meshes(volumes, interfaces, step_name, geometry_path)
    if config["snappyHexMeshSetup"].get("edgeMesh", False):
        write_edge_meshes(volumes, interfaces, geometry_path)
    if config["snappyHexMeshSetup"].get("refinementRegions", False):
        write_refinement_regions_meshes(volumes, geometry_path)

    # Write Dictionaries
    old_dict, new_dict = initialize_sHMD(config)
    if config["snappyHexMeshSetup"].get("generateBlockMeshDict", True):
        write_block_mesh_dict(model_bounding_box,config["snappyHexMeshSetup"]["backgroundMeshSize"])
    if not os.path.isfile("./system/meshQualityDict"): # Write base meshMeshQualityDict if one does not exits
        write_mesh_quality_dict()
    configure_sHMD_geometry(new_dict, volumes, interfaces, step_name, config)
    configure_sHMD_refinement_surfaces(new_dict, old_dict, volumes, interfaces, step_name, config)
    new_dict['castellatedMeshControls']['insidePoint'] = default_volume.inside_point
    # Edge mesh part here
    if config["snappyHexMeshSetup"].get("edgeMesh", False):
        configure_sHMD_feature_edges(new_dict, old_dict, volumes, interfaces, config)
    if config["snappyHexMeshSetup"].get("refinementRegions", False):
        configure_sHMD_refinement_regions(new_dict, old_dict, volumes, config)
    # Future layers here

    # Apply settings from previous sHMD
    if not config['snappyHexMeshSetup'].get('overwriteRefinements', False) and old_dict is not None:
        apply_previous_mesh_settings(new_dict, old_dict, config)
    write_sHMD(new_dict)

    # Write mesh split command
    write_split_command(default_volume.name)
    
    # Optionally view mesh
    if v:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open. Close gmsh window to continue.")
        gmsh.fltk.run()
        gmsh.fltk.finalize()
    print("All geometry files and scripts generated. Done.")
    # Last GMSH command
    gmsh.finalize()


def snappy_step_cleanup():
    gmsh.finalize()
    return

def main_func():
    parser = argparse.ArgumentParser(description='Process STEP geometry to generate STL files for SnappyHexMesh using GMSH')
    parser.add_argument('-v', action='store_true',help='Display generated surface mesh after genration') # view generated mesh in gmsh
    parser.add_argument('-vf', action='store_true',help='Display faces and labels. User can choose to continue or stop after inspecting output') # view faces after coherence and don't generate mesh
    parser.add_argument('-file',help='Specify filename if not in constant/(geometry||triSurface) directory or multiple step files are present')

    args = parser.parse_args()
    run_snappy_step(args.file, args.v,args.vf)

def snappy_step(file_name = None):
    run_snappy_step(file_name,False,False)

if __name__ == "__main__":
    main_func()