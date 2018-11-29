qx.Class.define("qxapp.dev.fake.lf.Data", {
  type: "static",

  statics: {
    itemList: {
      "defaultMaterials": [{
        key: "Dielectric-UUID",
        label: "Dielectric"
      }, {
        key: "PEC-UUID",
        label: "PEC"
      }, {
        key: "PMC-UUID",
        label: "PMC"
      }],

      "defaultBoundaries": [{
        key: "Dirichlet-UUID",
        label: "Dirichlet"
      }, {
        key: "Neumann-UUID",
        label: "Neumann"
      }, {
        key: "Flux-UUID",
        label: "Flux"
      }]
    },

    item: {
      "defaultMaterials": {
        "Dielectric-UUID": {
          "massDensity": {
            displayOrder: 0,
            label: "Mass Density",
            unit: "kg/m3",
            type: "number",
            defaultValue: 1.205
          },
          "electricConductivity": {
            displayOrder: 1,
            label: "Electric Conductivity",
            unit: "S/m",
            type: "number",
            defaultValue: 0
          },
          "electricRelativePermitivity": {
            displayOrder: 2,
            label: "Electric Relative Permittivity",
            unit: "",
            type: "number",
            defaultValue: 1
          },
          "magneticRelativePermeability": {
            displayOrder: 3,
            label: "Magnetic Relative Permeability",
            unit: "",
            type: "number",
            defaultValue: 1
          },
          "magneticConductivity": {
            displayOrder: 4,
            label: "Magnetic Conductivity",
            unit: "Ohm/m",
            type: "number",
            defaultValue: 0
          }
        }
      },

      "defaultBoundaries": {
        "Dirichlet-UUID": {
          "constantPotential": {
            displayOrder: 0,
            label: "Constant Potential",
            unit: "V",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        },
        "Neumann-UUID": {
          "normalDerivative": {
            displayOrder: 0,
            label: "Normal Derivative",
            unit: "V/m",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        },
        "Flux-UUID": {
          "constantFlux": {
            displayOrder: 0,
            label: "Constant Flux",
            type: "number",
            defaultValue: 0
          },
          "phase": {
            displayOrder: 1,
            label: "Phase",
            unit: "deg",
            type: "number",
            defaultValue: 0
          }
        }
      }
    },

    getItemList: function(simSettingsId) {
      let itemList = qxapp.dev.fake.lf.Data.itemList[simSettingsId];
      if (itemList) {
        itemList.sort(this.compare);
      }
      return itemList;
    },

    getItem: function(simSettingsId, itemId) {
      return qxapp.dev.fake.lf.Data.item[simSettingsId][itemId];
    }
  } // statics
});
