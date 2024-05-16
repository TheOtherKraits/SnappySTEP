import re


def regexStepBodyNames(fullPath): # Just regex all text?
    with open(fullPath, 'r') as StepFile:
        bodyNames = re.findall(r"MANIFOLD_SOLID_BREP\(\'(.*?)\'\,\#", StepFile.read())
        return bodyNames

def writeFoamDictionary(names: list[str],coordinate: list[float,float,float]) -> None:
    commands = [] # use append to add to list
    for i, element in enumerate(names):
        print("commands for ", element)
        # write foamDictinary command strings here for each object.
        # Commands for first object
        #if i == 1:


        # Geometry Section

        # Castellated Mesh Controls
    # write file
    fileName = "snappyStep.sh"
