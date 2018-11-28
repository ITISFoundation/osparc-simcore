import json
import os
import sys

import s4l_v1.document as document
from s4l_v1.simulation.emlf import MaterialSettings

here = os.path.dirname( sys.argv[0] if __name__ == '__name__' else __file__)

def make_key(m):
	return m.Name.replace(" ", "_") + "-UUID"


sims = document.AllSimulations
sim = sims[0]
materials = [s for s in sim.AllSettings if isinstance(s, MaterialSettings)]


path =  os.path.join(here, r'fake-materialDB-LF-getItemList.json')
with open(path, 'wt') as f:	
	data = [ { 
				'key': make_key(m), 
				'value': m.Name,
			 }	for m in materials]
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
	

path =  os.path.join(here, r'fake-materialDB-LF-getItem.json')
with open(path, 'wt') as f:	
	data = { make_key(m): create_item(m) for m in materials }
	json.dump(data, f, indent=2)
