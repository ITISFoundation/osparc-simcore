/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.LicensedItems", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__modelsCache = {};
  },

  statics: {
    VIP_MODELS: {
      HUMAN_BODY: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanWholeBody",
      HUMAN_BODY_REGION: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanBodyRegion",
      ANIMAL: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnimalWholeBody",
      PHANTOM: "https://speag.swiss/PD_DirectDownload/getDownloadableItems/ComputationalPhantom",
    },

    curateAnatomicalModels: function(anatomicalModelsRaw) {
      const anatomicalModels = [];
      const models = anatomicalModelsRaw["availableDownloads"];
      models.forEach(model => {
        const curatedModel = {};
        Object.keys(model).forEach(key => {
          if (key === "Features") {
            let featuresRaw = model["Features"];
            featuresRaw = featuresRaw.substring(1, featuresRaw.length-1); // remove brackets
            featuresRaw = featuresRaw.split(","); // split the string by commas
            const features = {};
            featuresRaw.forEach(pair => { // each pair is "key: value"
              const keyValue = pair.split(":");
              features[keyValue[0].trim()] = keyValue[1].trim()
            });
            curatedModel["Features"] = features;
          } else {
            curatedModel[key] = model[key];
          }
        });
        anatomicalModels.push(curatedModel);
      });
      return anatomicalModels;
    },
  },

  members: {
    __modelsCache: null,

    __fetchVipModels: async function(vipSubset) {
      if (!(vipSubset in this.self().VIP_MODELS)) {
        return [];
      }

      if (vipSubset in this.__modelsCache) {
        return this.__modelsCache[vipSubset];
      }

      return await fetch(this.self().VIP_MODELS[vipSubset], {
        method:"POST"
      })
        .then(resp => resp.json())
        .then(anatomicalModelsRaw => {
          const allAnatomicalModels = this.self().curateAnatomicalModels(anatomicalModelsRaw);
          const anatomicalModels = [];
          allAnatomicalModels.forEach(model => {
            const anatomicalModel = {};
            anatomicalModel["modelId"] = model["ID"];
            anatomicalModel["thumbnail"] = model["Thumbnail"];
            anatomicalModel["name"] = model["Features"]["name"] + " " + model["Features"]["version"];
            anatomicalModel["description"] = model["Description"];
            anatomicalModel["features"] = model["Features"];
            anatomicalModel["date"] = model["Features"]["date"];
            anatomicalModel["DOI"] = model["DOI"];
            anatomicalModels.push(anatomicalModel);
          });
          this.__modelsCache[vipSubset] = anatomicalModels;
          return anatomicalModels;
        });
    },

    fetchVipModels: async function(vipSubset) {
      const vipModels = this.self().VIP_MODELS;
      if (vipSubset && vipSubset in vipModels) {
        return await this.__fetchVipModels(vipSubset);
      }
      const promises = [];
      Object.keys(vipModels).forEach(sbs => promises.push(this.__fetchVipModels(sbs)));
      return await Promise.all(promises)
        .then(values => {
          const allVipModels = [];
          values.forEach(value => allVipModels.push(...value));
          return allVipModels;
        });
    },
  }
});
