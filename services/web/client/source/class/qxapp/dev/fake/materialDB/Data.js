qx.Class.define("qxapp.dev.fake.materialDB.Data", {
  type: "static",

  statics: {
    itemList: [
      {
        "label": "Air",
        "key": "Air-UUID"
      },
      {
        "label": "Cerebellum",
        "key": "Cerebellum-UUID"
      },
      {
        "label": "Cerebrospinal Fluid",
        "key": "Cerebrospinal_Fluid-UUID"
      },
      {
        "label": "Bronchi",
        "key": "Bronchi-UUID"
      },
      {
        "label": "Commissura Posterior",
        "key": "Commissura_Posterior-UUID"
      },
      {
        "label": "Blood",
        "key": "Blood-UUID"
      },
      {
        "label": "Commissura Anterior",
        "key": "Commissura_Anterior-UUID"
      },
      {
        "label": "Brain (White Matter)",
        "key": "Brain__White_Matter_-UUID"
      },
      {
        "label": "Cartilage",
        "key": "Cartilage-UUID"
      },
      {
        "label": "Brain (Grey Matter)",
        "key": "Brain__Grey_Matter_-UUID"
      },
      {
        "label": "Air 1",
        "key": "Air_1-UUID"
      },
      {
        "label": "Eye (Vitreous Humor)",
        "key": "Eye__Vitreous_Humor_-UUID"
      },
      {
        "label": "Eye (Lens)",
        "key": "Eye__Lens_-UUID"
      },
      {
        "label": "Skin",
        "key": "Skin-UUID"
      },
      {
        "label": "Dura",
        "key": "Dura-UUID"
      },
      {
        "label": "Esophagus Lumen",
        "key": "Esophagus_Lumen-UUID"
      },
      {
        "label": "Esophagus",
        "key": "Esophagus-UUID"
      },
      {
        "label": "Eye (Cornea)",
        "key": "Eye__Cornea_-UUID"
      },
      {
        "label": "Eye (Sclera)",
        "key": "Eye__Sclera_-UUID"
      },
      {
        "label": "Lymphnode",
        "key": "Lymphnode-UUID"
      },
      {
        "label": "Fat",
        "key": "Fat-UUID"
      },
      {
        "label": "Lung",
        "key": "Lung-UUID"
      },
      {
        "label": "Hippocampus",
        "key": "Hippocampus-UUID"
      },
      {
        "label": "Intervertebral Disc",
        "key": "Intervertebral_Disc-UUID"
      },
      {
        "label": "Medulla Oblongata",
        "key": "Medulla_Oblongata-UUID"
      },
      {
        "label": "Hypophysis",
        "key": "Hypophysis-UUID"
      },
      {
        "label": "Midbrain",
        "key": "Midbrain-UUID"
      },
      {
        "label": "Hypothalamus",
        "key": "Hypothalamus-UUID"
      },
      {
        "label": "Larynx",
        "key": "Larynx-UUID"
      },
      {
        "label": "Spinal Cord",
        "key": "Spinal_Cord-UUID"
      },
      {
        "label": "Nerve 2",
        "key": "Nerve_2-UUID"
      },
      {
        "label": "Pineal Body",
        "key": "Pineal_Body-UUID"
      },
      {
        "label": "Tendon Ligament",
        "key": "Tendon_Ligament-UUID"
      },
      {
        "label": "Thalamus",
        "key": "Thalamus-UUID"
      },
      {
        "label": "Muscle",
        "key": "Muscle-UUID"
      },
      {
        "label": "Pons",
        "key": "Pons-UUID"
      },
      {
        "label": "Salivary Gland",
        "key": "Salivary_Gland-UUID"
      },
      {
        "label": "Mucous Membrane",
        "key": "Mucous_Membrane-UUID"
      },
      {
        "label": "SAT (Subcutaneous Fat)",
        "key": "SAT__Subcutaneous_Fat_-UUID"
      },
      {
        "label": "Tongue",
        "key": "Tongue-UUID"
      },
      {
        "label": "Tooth",
        "key": "Tooth-UUID"
      },
      {
        "label": "Thyroid Gland",
        "key": "Thyroid_Gland-UUID"
      },
      {
        "label": "Trachea Lumen",
        "key": "Trachea_Lumen-UUID"
      },
      {
        "label": "Trachea",
        "key": "Trachea-UUID"
      },
      {
        "label": "Bone Marrow (Yellow)",
        "key": "Bone_Marrow__Yellow_-UUID"
      },
      {
        "label": "Bone (Cancellous)",
        "key": "Bone__Cancellous_-UUID"
      },
      {
        "label": "Bone (Cortical)",
        "key": "Bone__Cortical_-UUID"
      },
      {
        "label": "Skull Cortical",
        "key": "Skull_Cortical-UUID"
      },
      {
        "label": "Skull Cancellous",
        "key": "Skull_Cancellous-UUID"
      },
      {
        "label": "Silicone",
        "key": "Silicone-UUID"
      },
      {
        "label": "Fascicles",
        "key": "Fascicles-UUID"
      },
      {
        "label": "Epineurium",
        "key": "Epineurium-UUID"
      }
    ],

    item: {
      "Hypothalamus-UUID": {
        key: "Hypothalamus-UUID",
        version: "1.0.0",
        name: "Hypothalamus",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1044.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.23914873606449,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Hypophysis-UUID": {
        key: "Hypophysis-UUID",
        version: "1.0.0",
        name: "Hypophysis",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1053.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.4811,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Tongue-UUID": {
        key: "Tongue-UUID",
        version: "1.0.0",
        name: "Tongue",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1090.4,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.355286874117476,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Cerebellum-UUID": {
        key: "Cerebellum-UUID",
        version: "1.0.0",
        name: "Cerebellum",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1045.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.659666666666667,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Commissura_Anterior-UUID": {
        key: "Commissura_Anterior-UUID",
        version: "1.0.0",
        name: "Commissura Anterior",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1041.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.265075903212916,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Bone_Marrow__Yellow_-UUID": {
        key: "Bone_Marrow__Yellow_-UUID",
        version: "1.0.0",
        name: "Bone Marrow (Yellow)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 980.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.00247168316831683,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Medulla_Oblongata-UUID": {
        key: "Medulla_Oblongata-UUID",
        version: "1.0.0",
        name: "Medulla Oblongata",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1045.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.234006562252398,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Spinal_Cord-UUID": {
        key: "Spinal_Cord-UUID",
        version: "1.0.0",
        name: "Spinal Cord",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1075.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.234006562252398,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Skull_Cortical-UUID": {
        key: "Skull_Cortical-UUID",
        version: "1.0.0",
        name: "Skull Cortical",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1908.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.32,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Cerebrospinal_Fluid-UUID": {
        key: "Cerebrospinal_Fluid-UUID",
        version: "1.0.0",
        name: "CerebrospinalFluid",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1007.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1.7765,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Fat-UUID": {
        key: "Fat-UUID",
        version: "1.0.0",
        name: "Fat",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 911.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0573412363008279,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Eye__Sclera_-UUID": {
        key: "Eye__Sclera_-UUID",
        version: "1.0.0",
        name: "Eye (Sclera)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1032.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.62,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Cartilage-UUID": {
        key: "Cartilage-UUID",
        version: "1.0.0",
        name: "Cartilage",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1099.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1.01,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Mucous_Membrane-UUID": {
        key: "Mucous_Membrane-UUID",
        version: "1.0.0",
        name: "Mucous Membrane",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1102.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.355286874117476,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Trachea_Lumen-UUID": {
        key: "Trachea_Lumen-UUID",
        version: "1.0.0",
        name: "Trachea Lumen",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1.16409155293818,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Dura-UUID": {
        key: "Dura-UUID",
        version: "1.0.0",
        name: "Dura",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1174.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.367577227722772,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Skull_Cancellous-UUID": {
        key: "Skull_Cancellous-UUID",
        version: "1.0.0",
        name: "Skull Cancellous",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1178.33333333333,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 12320.035797440474,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.08152999458394551,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Tooth-UUID": {
        key: "Tooth-UUID",
        version: "1.0.0",
        name: "Tooth",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 2180.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0035039941902687,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Salivary_Gland-UUID": {
        key: "Salivary_Gland-UUID",
        version: "1.0.0",
        name: "Salivary Gland",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1048.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.67,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Eye__Vitreous_Humor_-UUID": {
        key: "Eye__Vitreous_Humor_-UUID",
        version: "1.0.0",
        name: "Eye (Vitreous Humor)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1004.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1.55,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Midbrain-UUID": {
        key: "Midbrain-UUID",
        version: "1.0.0",
        name: "Midbrain",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1045.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.234006562252398,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Lymphnode-UUID": {
        key: "Lymphnode-UUID",
        version: "1.0.0",
        name: "Lymphnode",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1035.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.293380448454906,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "SAT__Subcutaneous_Fat_-UUID": {
        key: "SAT__Subcutaneous_Fat_-UUID",
        version: "1.0.0",
        name: "SAT (Subcutaneous Fat)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 911.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0573412363008279,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Eye__Cornea_-UUID": {
        key: "Eye__Cornea_-UUID",
        version: "1.0.0",
        name: "Eye (Cornea)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1050.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.62,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Nerve_2-UUID": {
        key: "Nerve_2-UUID",
        version: "1.0.0",
        name: "Nerve 2",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1075.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.265075903212916,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Brain__Grey_Matter_-UUID": {
        key: "Brain__Grey_Matter_-UUID",
        version: "1.0.0",
        name: "Brain (Grey Matter)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1044.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.23914873606449,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Lung-UUID": {
        key: "Lung-UUID",
        version: "1.0.0",
        name: "Lung",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 394.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.104965456996338,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Thalamus-UUID": {
        key: "Thalamus-UUID",
        version: "1.0.0",
        name: "Thalamus",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1044.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.23914873606449,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Esophagus_Lumen-UUID": {
        key: "Esophagus_Lumen-UUID",
        version: "1.0.0",
        name: "Esophagus Lumen",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1.16409155293818,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Bronchi-UUID": {
        key: "Bronchi-UUID",
        version: "1.0.0",
        name: "Bronchi",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1101.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.231971604938272,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Commissura_Posterior-UUID": {
        key: "Commissura_Posterior-UUID",
        version: "1.0.0",
        name: "Commissura Posterior",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1041.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.265075903212916,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Epineurium-UUID": {
        key: "Epineurium-UUID",
        version: "1.0.0",
        name: "Epineurium",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1000.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.25,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Silicone-UUID": {
        key: "Silicone-UUID",
        version: "1.0.0",
        name: "Silicone",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1000.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1e-12,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Bone__Cortical_-UUID": {
        key: "Bone__Cortical_-UUID",
        version: "1.0.0",
        name: "Bone (Cortical)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1908.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0035039941902687,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Air-UUID": {
        key: "Air-UUID",
        version: "1.0.0",
        name: "Air",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1.205,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Hippocampus-UUID": {
        key: "Hippocampus-UUID",
        version: "1.0.0",
        name: "Hippocampus",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1044.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.275633903133903,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Tendon_Ligament-UUID": {
        key: "Tendon_Ligament-UUID",
        version: "1.0.0",
        name: "Tendon Ligament",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1142.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.367577227722772,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Esophagus-UUID": {
        key: "Esophagus-UUID",
        version: "1.0.0",
        name: "Esophagus",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1040.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.163535918367347,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Pons-UUID": {
        key: "Pons-UUID",
        version: "1.0.0",
        name: "Pons",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1045.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.234006562252398,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Fascicles-UUID": {
        key: "Fascicles-UUID",
        version: "1.0.0",
        name: "Fascicles",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1000.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.1,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Trachea-UUID": {
        key: "Trachea-UUID",
        version: "1.0.0",
        name: "Trachea",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1080.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.341986666666667,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Larynx-UUID": {
        key: "Larynx-UUID",
        version: "1.0.0",
        name: "Larynx",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1099.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1.01,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Muscle-UUID": {
        key: "Muscle-UUID",
        version: "1.0.0",
        name: "Muscle",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1090.4,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.355286874117476,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Thyroid_Gland-UUID": {
        key: "Thyroid_Gland-UUID",
        version: "1.0.0",
        name: "Thyroid Gland",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1050.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.4811,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Brain__White_Matter_-UUID": {
        key: "Brain__White_Matter_-UUID",
        version: "1.0.0",
        name: "Brain (White Matter)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1041.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.265075903212916,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Skin-UUID": {
        key: "Skin-UUID",
        version: "1.0.0",
        name: "Skin",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1109.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.17,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Air_1-UUID": {
        key: "Air_1-UUID",
        version: "1.0.0",
        name: "Air 1",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1.16409155293818,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Intervertebral_Disc-UUID": {
        key: "Intervertebral_Disc-UUID",
        version: "1.0.0",
        name: "Intervertebral Disc",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1099.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 1.01,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Pineal_Body-UUID": {
        key: "Pineal_Body-UUID",
        version: "1.0.0",
        name: "Pineal Body",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1053.0,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.4811,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Bone__Cancellous_-UUID": {
        key: "Bone__Cancellous_-UUID",
        version: "1.0.0",
        name: "Bone (Cancellous)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1178.33333333333,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.0820712643678161,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Eye__Lens_-UUID": {
        key: "Eye__Lens_-UUID",
        version: "1.0.0",
        name: "Eye (Lens)",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1075.5,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.345333333333333,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      },
      "Blood-UUID": {
        key: "Blood-UUID",
        version: "1.0.0",
        name: "Blood",
        inputs: {
          "RelativePermeability": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 4,
            "label": "Relative Permeability"
          },
          "MassDensity": {
            "defaultValue": 1049.75,
            "type": "number",
            "unit": "kg/m^3",
            "displayOrder": 0,
            "label": "Mass Density"
          },
          "RelativePermittivity": {
            "defaultValue": 1.0,
            "type": "number",
            "unit": "",
            "displayOrder": 2,
            "label": "Relative Permittivity"
          },
          "ElectricConductivity": {
            "defaultValue": 0.659851590289857,
            "type": "number",
            "unit": "S/m",
            "displayOrder": 1,
            "label": "Electric Conductivity"
          },
          "MagneticConductivity": {
            "defaultValue": 0.0,
            "type": "number",
            "unit": "Ohm/m",
            "displayOrder": 3,
            "label": "Magnetic Conductivity"
          }
        }
      }
    },

    compare: function(a, b) {
      if (a.label < b.label) {
        return -1;
      }
      if (a.label > b.label) {
        return 1;
      }
      return 0;
    },

    getItemList: function() {
      let itemList = qxapp.dev.fake.materialDB.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    },

    getItem: function(materialId) {
      if (materialId in qxapp.dev.fake.materialDB.Data.item) {
        return qxapp.dev.fake.materialDB.Data.item[materialId];
      }
      return null;
    }
  } // statics

});
