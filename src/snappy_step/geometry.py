import gmsh
import re

class volume:
    def __init__(self,tag, gmsh:gmsh):
        self.tag = tag
        self.gmsh = gmsh
        self.exterior_tags = []
        self.interface_tags = []
        self.exterior_patches = {}
        self.exterior_patch_edges = {}
        self.interface_patches = []
        self.name = gmsh.model.getEntityName(3,tag)
        self.face_dim_tags = gmsh.model.getBoundary([(3,tag)],False,False,False)
        self.inside_point = []
        for dim_tag in self.face_dim_tags:
            if len(gmsh.model.getAdjacencies(2,dim_tag[1])[0]) == 1:
                self.exterior_tags.append(dim_tag[1])
            else:
                self.interface_tags.append(dim_tag[1])
        
        for tag in self.exterior_tags:
            name = gmsh.model.getEntityName(2, tag)
            if not name:
                if self.name+"_default" in self.exterior_patches:
                    self.exterior_patches[self.name+"_default"].append(tag)
                    self.exterior_patch_edges[self.name+"_default"].update(gmsh.model.get_adjacencies(2,tag)[1])
                else:
                    self.exterior_patches[self.name+"_default"] = [tag]
                    self.exterior_patch_edges[self.name+"_default"] = set(gmsh.model.get_adjacencies(2,tag)[1])

            elif name in self.exterior_patches:
                self.exterior_patches[name].append(tag)
                self.exterior_patch_edges[name].update(gmsh.model.get_adjacencies(2,tag)[1])
            else:
                self.exterior_patches[name] = [tag]
                self.exterior_patch_edges[name] = set(gmsh.model.get_adjacencies(2,tag)[1])

    def getInsidePoint(self,config:dict):
        if "locationInMesh" in config and self.name in config["locationInMesh"]:
            self.inside_point =  config["locationInMesh"][self.name]
            print(f"Using coordiantes in config file for {self.name}.")
        else:
            self.inside_point = get_location_in_mesh(self)
        
        
class interface:
    def __init__(self, volume_1:volume, volume_2:volume, name:str, face_tags:list[int],edge_tags:set[int]):
        self.volume_pair = {volume_1, volume_2}
        self.face_tags = face_tags
        self.name = name
        self.edge_tags = edge_tags
        self.cell_zone_volume = None
        

def process_geometry(gmsh:gmsh,config:dict):
    volumes = []
    interfaces = []
    volume_dim_tags = gmsh.model.getEntities(3)
    for dim_tag in volume_dim_tags:
        volumes.append(volume(dim_tag[1],gmsh))
    for element in volumes:
        element.getInsidePoint(config)
    for index_a, volume_a in enumerate(volumes):
        for index_b, volume_b in enumerate(volumes):
            if index_b <= index_a:
                continue
            overlap = list(set(volume_a.interface_tags) & set(volume_b.interface_tags))
            if len(overlap)>0:
                volume_name_pair = [volume_a.name, volume_b.name]
                volume_name_pair.sort()
                default_interface_name = volume_name_pair[0]+"_"+volume_name_pair[1]+"_interface"
                groups = {}
                for tag in overlap:
                    name = gmsh.model.getEntityName(2, tag)
                    if not name:
                        if default_interface_name not in groups:
                            groups[default_interface_name] = [tag]
                        else:
                            groups[default_interface_name].append(tag)
                    else:
                        if name not in groups:
                            groups[name] = [tag]
                        else:
                            groups[name].append(tag)
                for interface_name in groups:
                    edges = set()
                    for face in groups[interface_name]:       
                        edges.update(set(gmsh.model.getAdjacencies(2, face)[1]))
                    interfaces.append(interface(volume_a,volume_b,interface_name,groups[interface_name],edges))
                    volume_a.interface_patches.append(interfaces[-1])
                    volume_b.interface_patches.append(interfaces[-1])
    return volumes, interfaces

                            
def get_location_in_mesh(entity:volume):
    coordinates = []
    # First try center of mass
    coordinates = list(entity.gmsh.model.occ.getCenterOfMass(3,entity.tag))
    if gmsh.model.isInside(3,entity.tag,coordinates):
        print("Found by center of mass")
        print(coordinates)
        return coordinates
    # try center of bounding box
    xmin, ymin, zmin, xmax, ymax, zmax = entity.gmsh.model.getBoundingBox(3,entity.tag)
    coordinates = [(xmax+xmin)/2,(ymax+ymin)/2,(zmax+zmin)/2]

    if gmsh.model.isInside(3,entity.tag,coordinates):
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
                if gmsh.model.isInside(3,entity.tag,coordinates):
                    print("Found by grid search")
                    print(coordinates)
                    return coordinates
    print("Point not found.")
    exit(1)

def validate_name(name: str):
    if name.startswith("."):
        name = name.lstrip(".")
    name = name.split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return name

def linspace(a, b, n):
    diff = (float(b) - a)/(n - 1)
    return [diff * i + a  for i in range(1, n-1)] # Skips first and last

def validate_gmsh_names(gmsh:gmsh):
    dim_tags = gmsh.model.getEntities(-1)
    for dim_tag in dim_tags:
        name = gmsh.model.getEntityName(dim_tag[0], dim_tag[1])
        if name:
            name = validate_name(name)
            gmsh.model.setEntityName(dim_tag[0], dim_tag[1], name)

def load_step_file(gmsh:gmsh, file_path, config):
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit
    # Set Import Scaling
    if "gmsh" in config:
        if "scaling" in config["gmsh"]:
            gmsh.option.setNumber("Geometry.OCCScaling",config["gmsh"]["scaling"])
    print('Reading geometry')
    gmsh.model.occ.importShapes(file_path,False)
    gmsh.model.occ.synchronize()

def imprint_geometry(gmsh:gmsh):
    # How many volumes before coherence
    number_volumes = len(gmsh.model.getEntities(3))

    # Remove extra names face names. Prevent issues when tags change.
    remove_face_labels_on_volumes(gmsh)

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    if number_volumes > 1:
        gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(3))
        gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(2))
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    # Check coherence results
    volumes = gmsh.model.getEntities(3)
    if len(volumes) != number_volumes:
        print("Coherence changed number of volumes. Check geometry. Exiting")
        gmsh.finalize()
        exit(1)

def remove_face_labels_on_volumes(gmsh:gmsh):
    faces = gmsh.model.getEntities(2)
    for face in faces:
        adjacent = gmsh.model.getAdjacencies(face[0],face[1])
        if adjacent[0].size > 0:
            name = gmsh.model.getEntityName(face[0],face[1])
            if name is not None:
                gmsh.model.removeEntityName(name)
                print("removed "+ name)

def assign_cell_zones_to_interfaces(volumes:list[volume]) -> volume:
    volumes.sort(key=lambda x: len(x.interface_patches), reverse=False)
    for element in volumes:
        if element == volumes[-1]:
            return element
        for surface in element.interface_patches:
            if surface.cell_zone_volume is None:
                surface.cell_zone_volume = element
                break
            else:
                continue
                
def generate_surface_mesh(gmsh:gmsh,config:dict):
    print("Generating Surface Mesh")
    gmsh.option.setNumber("Mesh.Algorithm",config["gmsh"]["meshAlgorithm"])
    gmsh.option.setNumber("Mesh.MeshSizeFactor",config["gmsh"]["meshSizeFactor"])
    gmsh.option.setNumber("Mesh.MeshSizeMin",config["gmsh"]["meshSizeMin"])
    gmsh.option.setNumber("Mesh.MeshSizeMax",config["gmsh"]["meshSizeMax"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature",config["gmsh"]["meshSizeFromCurvature"])
    gmsh.model.mesh.generate(2)

    # export settings
    gmsh.option.set_number("Mesh.StlOneSolidPerSurface",2)

        
