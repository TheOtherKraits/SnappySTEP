import re

def findNameLines(StepFile):
    for line in StepFile:
        if 'MANIFOLD_SOLID_BREP' in line:
            yield line

def getStepBodyNames(fullPath):
    Names = []
    with open(fullPath, 'r') as StepFile:
        for line in findNameLines(StepFile):
            Names.append = re.search(r"MANIFOLD_SOLID_BREP\(\'(.*?)\'\,\#"gm, StepFile)

def regexStepBodyNames(fullPath): # Just regex all text?
    with open(fullPath, 'r') as StepFile:
        bodyNames = re.findall(r"MANIFOLD_SOLID_BREP\(\'(.*?)\'\,\#"gm, StepFile)
        return bodyNames

