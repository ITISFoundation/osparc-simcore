import json
import os
import re
import sys
from collections import defaultdict

import s4l_v1.document as document
from s4l_v1.simulation.emlf import MaterialSettings

here = os.path.dirname( sys.argv[0] )


PATTERN = re.compile(r'\W')
def make_key(m):
    return PATTERN.sub("_", m.Name) + "-UUID"

sims = document.AllSimulations
sim = sims[0]
materials = [s for s in sim.AllSettings if isinstance(s, MaterialSettings)]



def create_material_getitemlist(materials):
    path =  os.path.join(here, r'fake-materialDB-LF-getItemList.json')
    with open(path, 'wt') as f:    
        data = [dict(key=make_key(m), label=m.Name) for m in materials]
        json.dump(data, f, indent=2)

def create_item(m):
    props = [
     m.MassDensityProp,
     m.ElectricProps.ConductivityProp,
     m.ElectricProps.RelativePermittivityProp,
     m.MagneticProps.ConductivityProp,
     m.MagneticProps.RelativePermeabilityProp,
    ]
    
    result = {}
    for index, prop in enumerate(props):
        result[prop.Name.replace(" ", "")] = {
        'displayOrder': index,
        'label': prop.Name,
        'unit':  str(prop.Unit or ""),
        'type': "number",
        'defaultValue': prop.Value
        }

    return result
    

def create_material_getitem(materials):
    path =  os.path.join(here, r'fake-materialDB-LF-getItem.json')
    with open(path, 'wt') as f:    
        data = { make_key(m): create_item(m) for m in materials }
        json.dump(data, f, indent=2)


def create_material2entities(sim):
    def create_map(sim):
        result = defaultdict(list)
        for c in sim.AllComponents:
            materials = [s for s in c.ListSettings() if isinstance(s, MaterialSettings)]
            for m in materials:
                result[make_key(m)].append(make_key(c))
        return result

    path =  os.path.join(here, r'fake-materialDB-LF-Material2Entities.json')
    with open(path, 'wt') as f:    
        data = create_map(sim)
        json.dump(data, f, indent=2)


def get_name(ent):
    name = ent.Name
    group = ent.ParentGroup()
    while group:
        name = group.Name + "/" + name
        group = group.ParentGroup()
    name = name.replace("Model/", "")
    return name

path =  os.path.join(here, r'fake-modeler-LF-getItemList.json')
with open(path, 'wt') as f:
    data = [ dict(key=make_key(c), label=get_name(c.Geometry)) for c in sim.AllComponents if c.Geometry ]
    json.dump(data, f, indent=2)
