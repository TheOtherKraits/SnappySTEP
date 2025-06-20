import re
import os
from foamlib import FoamFile, FoamCase
import math

    
def get_volume_names(gmsh):
    entities = gmsh.model.getEntities(3)
    names = []
    for entity in entities:
        long_name = gmsh.model.getEntityName(entity[0], entity[1])
        names.append(long_name.split("/")[-1]) # Return substring after last slash
        names = validate_names(names)
    return names, entities

def get_surface_names(gmsh):
    entities = gmsh.model.getEntities(2)
    names = []
    tags = []
    patch_tags = []
    for entity in entities:
        long_name = gmsh.model.getEntityName(entity[0], entity[1])
        name = long_name.split("/")[-1]
        if not name:
            continue
        elif name in names:
            idx = names.index(name)
            tags[idx].append(entity)
            patch_tags.append(entity[1])
        else:
            names.append(name) # Return substring after last slash
            tags.append([entity])
            patch_tags.append([entity])
    names = validate_names(names)
    return names, tags, patch_tags


def write_commands(file_name: str, commands: list):
    with open(file_name, 'w') as script:
        script.write("\n".join(commands))


def write_sHMD_feature_edges(new_dict:dict, names: list[str], old_dict:dict, default_level):
    new_dict["snapControls"]["explicitFeatureSnap"] = True
    new_dict["snapControls"]["implicitFeatureSnap"] = False
    for iter, name in enumerate(names):
        if old_dict is not None:
            try:
                level = old_dict["castellatedMeshControls"]["features"][iter]["level"]
            except:
                level = default_level
        else:
            level = default_level

        new_dict["castellatedMeshControls"]["features"].append({"file": "\"edges/"+name+"_edge.vtk\"", "level": level})


def write_sHMD_Geo(new_dict:dict, name: str, regions: list[str]) -> None:
    # file = FoamFile("./system/snappyHexMeshDict")
    new_dict["geometry"][name] = {}
    new_dict["geometry"][name]["type"] = "triSurfaceMesh"
    new_dict["geometry"][name]["file"] = "\""+name+".stl"+"\""
    if regions: # Check if not empty
        new_dict["geometry"][name]["regions"] = {}
        for i, element in enumerate(regions):
            new_dict["geometry"][name]["regions"][element] = {}
            new_dict["geometry"][name]["regions"][element]["name"] = element

def initialize_sHMD():
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
    return old_sHMD, new_dict

def check_old_dict(old_dict, key, default_value):
    if old_dict is not None and key in old_dict:
        return old_dict[key]
    else:
        return default_value


def write_sHMD_refinement_surfaces_cellZone(new_dict:dict,names: list[str],pairs: list[int, int],volume_names: list[str],volume_tags: list[int],coordinate: list[float,float,float]) -> None:
    number_contacts = []
    flat_pairs = sum(pairs, []) # flattens pairs list into single list
    for i, element in enumerate(volume_tags):
        number_contacts.append(flat_pairs.count(element)) # counts number of interfaces for each volume
    # Sort volumes by number of contacts
    number_contacts, volume_tags, volume_names, coordinate = zip(*sorted(zip(number_contacts, volume_tags, volume_names,coordinate)))
    # file = FoamFile("./system/snappyHexMeshDict")
    for element_index, element in enumerate(volume_names):
        if element == volume_names[-1]:
            new_dict["castellatedMeshControls"]["insidePoint"] = coordinate[i]
            break
        element_tag = volume_tags[element_index] # Tag of volume
        for tag_index, tag in enumerate(pairs): # Find first insance of volume in pairs
            if element_tag in tag:
                break
            else:
                continue
        new_dict["castellatedMeshControls"]["refinementSurfaces"][names[tag_index]]["cellZone"] = element
        new_dict["castellatedMeshControls"]["refinementSurfaces"][names[tag_index]]["mode"] = "insidePoint"
        new_dict["castellatedMeshControls"]["refinementSurfaces"][names[tag_index]]["insidePoint"] = coordinate[i]
        # remove used interface from list
        names.pop(tag_index)
        pairs.pop(tag_index)
    return element


def write_sHMD_refinement_surfaces(new_dict: dict, name: str, regions: list[str], old_dict, default_level: list[int]) -> None:
    if regions: # Check if empty
        if old_dict is not None:
            try:
                level = old_dict["castellatedMeshControls"]["refinementSurfaces"][name]["level"]
            except:
                level = default_level
        else:
            level = default_level
        new_dict["castellatedMeshControls"]["refinementSurfaces"][name] = {"level": level, "patchInfo": {"type": "wall"},"regions": {}}
        for i, element in enumerate(regions):
            if old_dict is not None:
                try:
                    level = old_dict["castellatedMeshControls"]["refinementSurfaces"][name]["regions"][element]["level"]
                except:
                    level = default_level
            else:
                level = default_level
            new_dict["castellatedMeshControls"]["refinementSurfaces"][name]["regions"][element] = {"level": level, "patchInfo": {"type": "wall"}}
    else:
        if old_dict is not None:
            try:
                level = old_dict["castellatedMeshControls"]["refinementSurfaces"][name]["level"]
            except:
                level = default_level
        else:
            level = default_level
        if name not in new_dict["castellatedMeshControls"]["refinementSurfaces"]:
            new_dict["castellatedMeshControls"]["refinementSurfaces"][name] = {}
        new_dict["castellatedMeshControls"]["refinementSurfaces"][name]["faceZone"] = name
        new_dict["castellatedMeshControls"]["refinementSurfaces"][name]["level"] = level
        new_dict["castellatedMeshControls"]["refinementSurfaces"][name]["patchInto"] = {"type": "wall"}
  

def write_split_command(default_zone: str):
    commands = []
    commands.append("splitMeshRegions -cellZones -defaultRegionName " + default_zone + " -useFaceZones -overwrite")
    file_name = "snappyStepSplitMeshRegions.sh"
    write_commands(file_name,commands)
 

def flatten(arg):
    if not isinstance(arg, list): # if not list
        return [arg]
    return [x for sub in arg for x in flatten(sub)]


def set_sHMD_external_patch(new_dict:dict, region_list: list, name: str):
    for region in region_list:
        new_dict["castellatedMeshControls"]["refinementSurfaces"][name]["regions"][region]["patchInfo"]["type"] = "patch"


def validate_names(names: list[str]):
    for name_index, name in enumerate(names):
        if name.startswith("."):
            name = name.lstrip(".")
        names[name_index] = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    return names

def get_location_in_mesh(gmsh, volume_tag: int):
    coordinates = []
    # First try center of mass
    coordinates = list(gmsh.model.occ.getCenterOfMass(3,volume_tag))
    
    if gmsh.model.isInside(3,volume_tag,coordinates):
        print("Found by center of mass")
        print(coordinates)
        return coordinates
    
    # try center of bounding box
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(3,volume_tag)
    coordinates = [(xmax+xmin)/2,(ymax+ymin)/2,(zmax+zmin)/2]

    if gmsh.model.isInside(3,volume_tag,coordinates):
        print("Found by bounding box center")
        print(coordinates)
        return coordinates

    # sweep through grids, increasingly fine. Choosing plane in cernter, sweeping though 2d locations on grid
    z = (zmax+zmin)/2
    grids = [10, 100, 1000]
    for element in grids: # coarse grid to fine grid
        x = linspace(xmin, xmax, element)
        y = linspace(ymin, ymax, element)
        print("Grid Search: "+str(element)+"x"+str(element))
        for xi in x:
            for yi in y:
                coordinates = [xi, yi, z]
                if gmsh.model.isInside(3,volume_tag,coordinates):
                    print("Found by grid search")
                    print(coordinates)
                    return coordinates

    print("Point not found.")
    exit(1)

def linspace(a, b, n):
    diff = (float(b) - a)/(n - 1)
    return [diff * i + a  for i in range(1, n-1)] # Skips first and last

def remove_face_labels_on_volumes(gmsh):
    faces = gmsh.model.getEntities(2)
    for face in faces:
        adjacent = gmsh.model.getAdjacencies(face[0],face[1])
        if adjacent[0].size > 0:
            name = gmsh.model.getEntityName(face[0],face[1])
            if name != "":
                gmsh.model.removeEntityName(name)
                print("removed "+ name)
def write_edge_mesh(gmsh, surfaces: list, name: str, geometry_path: str):
    edges = set() # using set to avoid duplicates
    for face in surfaces:
        edges.update(gmsh.model.getAdjacencies(2,face)[1]) # add edge tags to set
    gmsh.model.addPhysicalGroup(1,list(edges),-1,name)
    print("Writing " + os.path.join(geometry_path,name+"_edge.vtk"))
    if not os.path.exists(os.path.join(geometry_path,"edges")):
        os.makedirs(os.path.join(geometry_path,"edges"))
    gmsh.write(os.path.join(geometry_path,"edges",name+"_edge.vtk"))
    print("Done.")
    gmsh.model.removePhysicalGroups([])

def ask_yes_no(question):
    while True:
        response = input(f"{question} (yes or no): ").lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no' (y/n).")
def get_geometry_path(): 
    geometry_path = "./constant/geometry"
    if not os.path.exists(geometry_path):
        geometry_path = "./constant/triSurface"
        if not os.path.exists(geometry_path):
            geometry_path = None
    return geometry_path

def write_sHMD(new_dict):
    fn = "./system/snappyHexMeshDict"
    if os.path.isfile(fn):
        os.remove(fn)
    file = FoamFile("./system/snappyHexMeshDict") # Load snappyHexMeshDict
    for key in new_dict:
        file[key] = new_dict[key]

def read_snappy_step_dict():
    file = FoamFile("./system/snappyStepDict")
    print(file)

def write_block_mesh_dict(bouding_box:list,dx:list[float]):
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

            
def write_snappy_step_dict_template():
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
    file["snappyHexMeshSetup"] = {"edgeMesh": True, "multiRegionFeatureSnap": True, "generateBlockMeshDict": True, "backgroundMeshSize": [0.01, 0.01, 0.01], "defaultSurfaceRefinement": [2, 2],"defaultEdgeRefinement": 1, "overwriteRefinements": False}
    file["locationInMesh"] = {}
 
def read_snappy_step_dict():
    file_path = "./system/snappyStepDict"
    file = FoamFile(file_path)
    return file.as_dict()

def write_mesh_quality_dict():
    file_path = "./system/meshQualityDict"
    file = FoamFile(file_path)
    file["#includeEtc"] = "\"caseDicts/mesh/generation/meshQualityDict.cfg\""

def retrive_old_dict_user_entries(old_dict, new_dict):
    for key, value in old_dict:
        if key == "geometry":
            continue
        elif key == "refinementSurfaces":
            continue
        elif key == "refinementRegions":
            continue
        elif isinstance(value, dict) and key in new_dict:
            retrive_old_dict_user_entries(old_dict[key], new_dict[key])
        elif key not in new_dict and (isinstance(value, str) or isinstance(value, int) or isinstance(value, float)):
            new_dict[key] = value
        else:
            continue
            

    