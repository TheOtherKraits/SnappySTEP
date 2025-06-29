import os
import math

import gmsh
from foamlib import FoamFile, FoamCase

from .geometry import validate_name, Volume, Interface


def get_geometry_path(): 
    """ TODO """
    geometry_path = "./constant/geometry"
    if not os.path.exists(geometry_path):
        geometry_path = "./constant/triSurface"
        if not os.path.exists(geometry_path):
            geometry_path = None
    if geometry_path is None:
        print("Please run from OpenFOAM case root directory.")
        exit(1)
    return geometry_path

def read_config() -> dict:
    """ TODO """
    try:
        config = read_snappy_step_dict()
    except:
        print("There seems to be a problem with snappyStepDict. Please check for format errors. Exiting.")
        exit(1)

    if "locationInMesh" in config:
        if config["locationInMesh"]:
            print("Using locationInMesh coordinates defined in config")
            new_locations = {}
            for old_key, value in config["locationInMesh"].items():
                new_key = validate_name(old_key)
                new_locations[new_key] = value
            config["locationInMesh"] = new_locations

    else:
        config["locationInMesh"] = []

    if "edgeMesh" in config["snappyHexMeshSetup"]:
        edge_mesh = config["snappyHexMeshSetup"]["edgeMesh"]
        if edge_mesh:
            print("Edge mesh files will be generated")
    else:
        edge_mesh = False
    return config

def read_snappy_step_dict() -> dict:
    """ TODO """
    file_path = "./system/snappyStepDict"
    file = FoamFile(file_path)
    return file.as_dict()

def find_geometry_file(file_name: str, geometry_path: str) -> str:
    """ TODO """
    # Find geometry files
    extension = [".stp", ".step", ".STP", ".STEP"]
    files = []
    if file_name is None:
        for file in os.listdir(geometry_path):
            if file.endswith(tuple(extension)):
                files.append(file)
    
        if len(files) == 0:
            print("No step file found in constant/(geometry||triSurface) directory. Exiting.")
            exit(1)
        elif len(files) > 1:
            print("More than one step file found. Please remove or rename other files, or specify the filepath to read with the -file arguemnt. Exiting.")
            exit(1)   
        else:
            print(files[0]+" found")
            step_file = os.path.join(geometry_path, files[0])
    else:
        if os.path.isfile(file_name):
            step_file = file_name
        else:
            print(file_name + " is not a file. Exiting.")
            exit(1)
    return step_file

def write_snappy_step_dict_template():
    """
    Write snappy step dictionary template file. 
    File should be at ./system/snappyStepDict
    """
    file_path = "./system/snappyStepDict"
    file = FoamFile(file_path)
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except PermissionError:
            print(f"Error: Permission denied to delete '{file_path}'.")
        except OSError as e:
            print(f"Error: Could not delete '{file_path}'. Reason: {e}")
    file["gmsh"] = {"meshSizeMax": 1000, "meshSizeMin": 0,"meshSizeFactor": 1,"meshSizeFromCurvature": 90,"meshAlgorithm": 6, "scaling": 1}
    file["snappyHexMeshSetup"] = {"edgeMesh": True, "refinementRegions": False,"multiRegionFeatureSnap": True, "generateBlockMeshDict": True, "backgroundMeshSize": [0.01, 0.01, 0.01], "defaultSurfaceRefinement": [2, 2],"defaultEdgeRefinement": 1, "defaultRegionRefinement": [[1, 2]], "overwriteRefinements": False}
    file["locationInMesh"] = {}

def write_block_mesh_dict(bouding_box: list, dx:list[float]):
    """ TODO """
    x_len = bouding_box[3]-bouding_box[0]
    y_len = bouding_box[4]-bouding_box[1]
    z_len = bouding_box[5]-bouding_box[2]
    x_cells = math.ceil(x_len/dx[0])
    y_cells = math.ceil(y_len/dx[1])
    z_cells = math.ceil(z_len/dx[2])
    x_buffer = ((x_cells*dx[0])-x_len)/2.0
    y_buffer = ((y_cells*dx[1])-y_len)/2.0
    z_buffer = ((z_cells*dx[2])-z_len)/2.0
    vertices = [
            ["$xMin", "$yMin", "$zMin"],
            ["$xMax", "$yMin", "$zMin"],
            ["$xMax", "$yMax", "$zMin"],
            ["$xMin", "$yMax", "$zMin"],
            ["$xMin", "$yMin", "$zMax"],
            ["$xMax", "$yMin", "$zMax"],
            ["$xMax", "$yMax", "$zMax"],
            ["$xMin", "$yMax", "$zMax"]
            ]
    blocks = ["hex", [0, 1, 2, 3, 4, 5, 6, 7], ["$xCells", "$yCells", "$zCells"], "simpleGrading", [1, 1, 1]]
    fn = "./system/blockMeshDict"
    if os.path.isfile(fn):
        os.remove(fn)
    case = FoamCase(".")
    with case.block_mesh_dict as file: # Load Dict
        file["defaultPatch"]={"name":  "background", "type": "patch"}
        file["xMin"] = bouding_box[0] - x_buffer
        file["xMax"] = bouding_box[3] + x_buffer
        file["yMin"] = bouding_box[1] - y_buffer
        file["yMax"] = bouding_box[4] + y_buffer
        file["zMin"] = bouding_box[2] - z_buffer
        file["zMax"] = bouding_box[5] + z_buffer
        file["xCells"] = x_cells
        file["yCells"] = y_cells
        file["zCells"] = z_cells
        file["scale"] = 1

        if "vertices" not in file.as_dict():
            file["vertices"] = vertices
        elif file["vertices"] != vertices:
            file["vertices"] = vertices
        file["blocks"] = blocks
        if "edges" not in file.as_dict():
            file["edges"] = []
            
        if "mergePatchPairs" not in file.as_dict():
            file["mergePatchPairs"] = []

def retrive_old_dict_user_entries(old_dict, new_dict):
    """ TODO """
    for key, value in old_dict:
        if key in [ "geometry", "refinementSurfaces", "refinementRegions"]:
            # Skip these keys - values should not be copied to new dict
            continue
        elif isinstance(value, dict) and key in new_dict:
            retrive_old_dict_user_entries(old_dict[key], new_dict[key])
        elif key not in new_dict and (isinstance(value, str) or isinstance(value, int) or isinstance(value, float)):
            new_dict[key] = value
        else:
            continue

def write_mesh_quality_dict():
    """ TODO """
    file_path = "./system/meshQualityDict"
    file = FoamFile(file_path)
    file["#includeEtc"] = "\"caseDicts/mesh/generation/meshQualityDict.cfg\""

def write_sHMD(new_dict):
    """ TODO """
    fn = "./system/snappyHexMeshDict"
    if os.path.isfile(fn):
        os.remove(fn)
    file = FoamFile("./system/snappyHexMeshDict") # Load snappyHexMeshDict
    for key in new_dict:
        file[key] = new_dict[key]

def ask_yes_no(question):
    """ TODO """
    while True:
        response = input(f"{question} (yes or no): ").lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no' (y/n).")

def initialize_sHMD(config: dict):
    """ TODO """
    file = FoamFile("./system/snappyHexMeshDict")
    try:
        old_sHMD = file.as_dict()
    except:
        old_sHMD = None
    new_dict = {}
    new_dict["#includeEtc"] = "\"caseDicts/mesh/generation/snappyHexMeshDict.cfg\""
    new_dict["castellatedMesh"] = check_old_dict(old_sHMD,"castellatedMesh", "on")
    new_dict["snap"] = check_old_dict(old_sHMD,"snap", "on")
    new_dict["addLayers"] = check_old_dict(old_sHMD,"addLayers", "off")
    new_dict["geometry"] = {}
    new_dict["castellatedMeshControls"] = {}
    new_dict["castellatedMeshControls"]["features"] = []
    new_dict["castellatedMeshControls"]["refinementSurfaces"] = {}
    new_dict["snapControls"] = {}
    new_dict["mergeToleance"] = check_old_dict(old_sHMD,"mergeTolerance", 1e-6)
    if "multiRegionFeatureSnap" in config["snappyHexMeshSetup"]:
        new_dict["snapControls"]["multiRegionFeatureSnap"] = config["snappyHexMeshSetup"]["multiRegionFeatureSnap"]
    return old_sHMD, new_dict

def check_old_dict(old_dict, key, default_value):
    """ TODO """
    if old_dict is not None and key in old_dict:
        return old_dict[key]
    else:
        return default_value
    
def write_split_command(default_zone: str):
    """ TODO """
    commands = []
    commands.append("splitMeshRegions -cellZones -defaultRegionName " + default_zone + " -useFaceZones -overwrite")
    file_name = "snappyStepSplitMeshRegions.sh"
    write_commands(file_name,commands)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

def write_commands(file_name: str, commands: list):
    """ TODO """
    with open(file_name, 'w') as script:
        script.write("\n".join(commands))

def write_surface_meshes(volumes: list[Volume],interfaces: list[Interface], step_name, path):
    """ TODO """
    # Exterior Patches, single file
    gmsh.model.removePhysicalGroups([])
    for instance in volumes:
        for patch, tags in instance.exterior_patches.items():
            gmsh.model.addPhysicalGroup(2,tags,-1,patch)
    gmsh.write(os.path.join(path,step_name+".stl"))
    gmsh.model.removePhysicalGroups([])

    # Interfaces, one per file
    for instance in interfaces:
        gmsh.model.removePhysicalGroups([])
        gmsh.model.addPhysicalGroup(2,instance.face_tags, -1, instance.name)
        gmsh.write(os.path.join(path,instance.name+".stl"))
    gmsh.model.removePhysicalGroups([])

def write_refinement_regions_meshes(volumes: list[Volume], path):
    gmsh.model.removePhysicalGroups([])
    for instance in volumes:
        gmsh.model.addPhysicalGroup(2,instance.exterior_tags + instance.interface_tags, -1, instance.name+"_refinement_region")
        gmsh.write(os.path.join(path,instance.name+"_refinement_region.stl"))
        gmsh.model.removePhysicalGroups([])

def write_edge_meshes(volumes: list[Volume],interfaces: list[Interface], path):
    """ TODO """
    if not os.path.exists(os.path.join(path,"edges")):
        os.makedirs(os.path.join(path,"edges"))
    gmsh.model.removePhysicalGroups([])
    for instance in volumes:
        for patch, tags in instance.exterior_patch_edges.items():
            gmsh.model.addPhysicalGroup(1,list(tags),-1,patch)
            gmsh.write(os.path.join(path,"edges",patch+"_edge.vtk"))
    gmsh.model.removePhysicalGroups([])

    for instance in interfaces:
        gmsh.model.removePhysicalGroups([])
        gmsh.model.addPhysicalGroup(1,list(instance.edge_tags),-1,instance.name)
        gmsh.write(os.path.join(path,"edges",instance.name+"_edge.vtk"))
    gmsh.model.removePhysicalGroups([])
        
def configure_sHMD_geometry(new_dict: dict, volumes: list[Volume],interfaces: list[Interface],step_name: str, config:dict):
    """ TODO """
    # Geometry section
    new_dict["geometry"][step_name] = {}
    new_dict["geometry"][step_name]["type"] = "triSurfaceMesh"
    new_dict["geometry"][step_name]["file"] = "\""+step_name+".stl"+"\""
    new_dict["geometry"][step_name]["regions"] = {}
    for instance in volumes:
        for patch in instance.exterior_patches:
            new_dict["geometry"][step_name]["regions"][patch] = {"name":patch}
    for instance in interfaces:
        new_dict["geometry"][instance.name] = {"type":"triSurfaceMesh","file":f"\"{instance.name}_refinement_region.stl\""}
    if config["snappyHexMeshSetup"]["refinementRegions"]:
        for instance in volumes:
            new_dict["geometry"][instance.name] = {"type":"triSurfaceMesh","file":f"\"{instance.name}_refinement_region.stl\""}
    
 
def configure_sHMD_refinement_surfaces(new_dict: dict, old_dict: dict, volumes: list[Volume], interfaces: list[Interface], step_name: str, config: dict):
    """ TODO """
    # Exterior Surfaces
    if old_dict is not None and not config["snappyHexMeshSetup"]["overwriteRefinements"]:
        try:
            level = old_dict["castellatedMeshControls"]["refinementSurfaces"][step_name]["level"]
        except:
            level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
    else:
        level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
    new_dict["castellatedMeshControls"]["refinementSurfaces"][step_name] = {"level": level, "patchInfo": {"type": "wall"},"regions": {}}
    sub_strings = ["default", "wall"]
    for instance in volumes:
        for patch in instance.exterior_patches:
            if old_dict is not None and not config["snappyHexMeshSetup"]["overwriteRefinements"]:
                try:
                    level = old_dict["castellatedMeshControls"]["refinementSurfaces"][step_name]["regions"][patch]["level"]
                except:
                    level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
            else:
                level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
            if any(sub in patch for sub in sub_strings):
                patch_type = "wall"
            else:
                patch_type = "patch"
            new_dict["castellatedMeshControls"]["refinementSurfaces"][step_name]["regions"][patch] = {"level": level, "patchInfo": {"type": patch_type}}
    # Interfaces
    for instance in interfaces:
        if old_dict is not None and not config["snappyHexMeshSetup"]["overwriteRefinements"]:
            try:
                level = old_dict["castellatedMeshControls"]["refinementSurfaces"][instance.name]["level"]
            except:
                level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
        else:
            level = config["snappyHexMeshSetup"]["defaultSurfaceRefinement"]
        new_dict["castellatedMeshControls"]["refinementSurfaces"][instance.name] = {"faceZone": instance.name, "level": level, "patchInfo": {"type": "wall"}}
        if instance.cell_zone_volume is not None:
            new_dict["castellatedMeshControls"]["refinementSurfaces"][instance.name]["cellZone"] = instance.cell_zone_volume.name
            new_dict["castellatedMeshControls"]["refinementSurfaces"][instance.name]["mode"] = "insidePoint"
            new_dict["castellatedMeshControls"]["refinementSurfaces"][instance.name]["insidePoint"] = instance.cell_zone_volume.inside_point

def configure_sHMD_refinement_regions(new_dict: dict, old_dict: dict, volumes: list[Volume], config: dict):
    new_dict["castellatedMeshControls"]["refinementRegions"] = {}
    for instance in volumes:
        if old_dict is not None and not config["snappyHexMeshSetup"]["overwriteRefinements"]:
            try:
                level = old_dict["castellatedMeshControls"]["refinementRegions"][instance.name+"_refinement_region"]["level"]
            except:
                level = config["snappyHexMeshSetup"]["defaultRegionRefinement"]
        else:
            level = config["snappyHexMeshSetup"]["defaultRegionRefinement"]
        new_dict["castellatedMeshControls"]["refinementRegions"][instance.name+"_refinement_region"] = {"mode": "inside", "levels": level}

def configure_sHMD_feature_edges(new_dict, old_dict, volumes, interfaces, config):
    """ TODO """
    new_dict["snapControls"]["explicitFeatureSnap"] = True
    new_dict["snapControls"]["implicitFeatureSnap"] = False
    for instance in volumes:
        for patch in instance.exterior_patches:
            file_path = "\"edges/"+patch+"_edge.vtk\""
            set_edge_mesh_entry(new_dict, old_dict, file_path, config)
    for instance in interfaces:
        file_path = "\"edges/"+instance.name+"_edge.vtk\""
        set_edge_mesh_entry(new_dict, old_dict, file_path, config)


def find_last_edge_mesh_refinement(old_dict:dict, file_path:str):
    """ TODO """
    for entry in old_dict["castellatedMeshControls"]["features"]:
        if entry["file"] == file_path:
            return entry["level"]
    return None

def set_edge_mesh_entry(new_dict:dict, old_dict:dict, file_path:str, config):
    """ TODO """
    if old_dict is not None and not config["snappyHexMeshSetup"]["overwriteRefinements"]:
        level = find_last_edge_mesh_refinement(old_dict, file_path)
        if level is None:
            level = config["snappyHexMeshSetup"]["defaultEdgeRefinement"]
    else:
        level = config["snappyHexMeshSetup"]["defaultEdgeRefinement"]
    new_dict["castellatedMeshControls"]["features"].append({"file": file_path, "level": level})