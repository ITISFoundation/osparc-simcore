/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Services", {
  type: "static",

  statics: {
    __servicesCached: {},

    getServicesLatest: function(useCache = true) {
      return new Promise(resolve => {
        if (useCache && Object.keys(this.__servicesCached)) {
          // return latest only
          const latest = this.__getLatestCached();
          resolve(latest);
          return;
        }

        osparc.data.Resources.getInstance().getAllPages("servicesV2")
          .then(servicesArray => {
            const servicesObj = osparc.service.Utils.convertArrayToObject(servicesArray);
            this.__addHits(servicesObj);
            this.__addTSRInfos(servicesObj);
            this.__addExtraTypeInfos(servicesObj);

            Object.values(servicesObj).forEach(serviceKey => {
              Object.values(serviceKey).forEach(service => this.__addToCache(service));
            });

            resolve(servicesObj);
          })
          .catch(err => {
            const msg = err.message || qx.locale.Manager.tr("Unable to fetch Services");
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
            console.error(err);
          });
      });
    },

    __getVersions: function(key, filterDeprecated = true) {
      const services = this.__servicesCached;
      let versions = [];
      if (key in services) {
        const serviceVersions = services[key];
        versions = versions.concat(Object.keys(serviceVersions));
        if (filterDeprecated) {
          // OM: the list-latest-services endpoint doesn't return the "retired" info in its data anymore
          versions = versions.filter(version => {
            if (services[key][version]["retired"]) {
              return false;
            }
            return true;
          });
        }
        versions.sort(osparc.utils.Utils.compareVersionNumbers);
      }
      return versions.reverse();
    },

    getLatest: function(key) {
      const services = this.__servicesCached;
      if (key in services) {
        const versions = this.__getVersions(key);
        if (versions.length) {
          return services[key][versions[0]];
        }
      }
      return null;
    },

    getLatestCompatible: function(key, version) {
      const services = this.__servicesCached;
      if (key in services && version in services[key]) {
        const serviceMD = services[key][version];
        // OM: the list-latest-services endpoint doesn't return the "compatibility" info in its data anymore
        if (serviceMD["compatibility"] && serviceMD["compatibility"]["canUpdateTo"]) {
          const canUpdateTo = serviceMD["compatibility"]["canUpdateTo"];
          return {
            key: "key" in canUpdateTo ? canUpdateTo["key"] : key, // key is optional
            version: canUpdateTo["version"]
          }
        }
        // the provided key/version itself is the latest compatible
        return {
          key,
          version
        }
      }
      return null;
    },

    getVersionDisplay: function(key, version) {
      const services = this.__servicesCached;
      if (key in services && version in services[key]) {
        return osparc.service.Utils.extractVersionDisplay(services[key][version]);
      }
      return null;
    },

    getReleasedDate: function(key, version) {
      const services = this.__servicesCached;
      if (
        key in services &&
        version in services[key] &&
        "released" in services[key][version]
      ) {
        return services[key][version]["released"];
      }
      return null;
    },

    getService: function(key, version, useCache = true) {
      return new Promise(resolve => {
        if (
          useCache &&
          this.__isInCache(key, version) &&
          "history" in this.__servicesCached[key][version]
        ) {
          resolve(this.__servicesCached[key][version]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.fetch("servicesV2", "getOne", params)
          .then(service => {
            this.__addHit(service);
            this.__addTSRInfo(service);
            this.__addExtraTypeInfo(service);
            this.__addToCache(service)
            resolve(service);
          })
          .catch(console.error);
      });
    },

    populateVersionsSelectBox: function(key, selectBox) {
      const latest = this.getLatest(key);
      return this.getService(key, latest["version"])
        .then(latestMetadata => {
          latestMetadata["history"].forEach(entry => {
            const versionDisplay = osparc.service.Utils.extractVersionDisplay(entry);
            const listItem = new qx.ui.form.ListItem(versionDisplay);
            osparc.utils.Utils.setIdToWidget(listItem, "serviceVersionItem_" + versionDisplay);
            listItem.version = entry["version"];
            selectBox.add(listItem);
          });
        });
    },

    getServicesLatestList: function(excludeFrontend = true, excludeDeprecated = true) {
      return new Promise(resolve => {
        const servicesList = [];
        this.getServicesLatest()
          .then(async servicesLatest => {
            const serviceKeys = Object.keys(servicesLatest);
            for (let i=0; i<serviceKeys.length; i++) {
              const key = serviceKeys[i];
              let serviceLatest = servicesLatest[key];
              if (excludeFrontend && key.includes("simcore/services/frontend/")) {
                // do not add frontend services
                continue;
              }
              // OM: the list-latest-services endpoint doesn't return the "retired" info in its data anymore
              if (excludeDeprecated && serviceLatest["retired"]) {
                // first check if a previous version of this service isn't retired
                let versions = Object.keys(this.__servicesCached[key]);
                versions = versions.sort(osparc.utils.Utils.compareVersionNumbers).reverse();
                for (let j=0; j<versions.length; j++) {
                  const version = versions[j];
                  if (!this.__servicesCached[key][version]["retired"]) {
                    // one older non retired version found
                    serviceLatest = await this.getService(key, version);
                    break;
                  }
                }
                if (serviceLatest["retired"]) {
                  // do not add retired services
                  continue;
                }
              }
              servicesList.push(serviceLatest);
            }
          })
          .catch(err => {
            console.error(err);
          })
          .finally(() => resolve(servicesList));
      });
    },

    getResources: function(key, version) {
      return new Promise(resolve => {
        if (
          this.__isInCache(key, version) &&
          "resources" in this.__servicesCached[key][version]
        ) {
          resolve(this.__servicesCached[key][version]["resources"]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.get("serviceResources", params)
          .then(resources => {
            this.__servicesCached[key][version]["resources"] = resources;
            resolve(resources);
          });
      });
    },

    getMetadata: function(key, version) {
      if (this.__isInCache(key, version)) {
        return this.__servicesCached[key][version];
      }
      return null;
    },

    patchServiceData: function(serviceData, fieldKey, value) {
      const key = serviceData["key"];
      const version = serviceData["version"];
      const patchData = {};
      patchData[fieldKey] = value;
      const params = {
        url: osparc.data.Resources.getServiceUrl(key, version),
        data: patchData
      };
      return osparc.data.Resources.fetch("servicesV2", "patch", params)
        .then(() => {
          this.__servicesCached[key][version][fieldKey] = value;
          serviceData[fieldKey] = value;
        });
    },

    getStudyServicesMetadata: function(studyData) {
      const wbServices = new Set(osparc.study.Utils.extractUniqueServices(studyData["workbench"]));
      const promises = [];
      wbServices.forEach(srv => {
        promises.push(this.getService(srv["key"], srv["version"]));
      });
      return Promise.all(promises);
    },

    getInaccessibleServices: function(workbench) {
      const allServices = this.__servicesCached;
      const unaccessibleServices = [];
      const wbServices = new Set(osparc.study.Utils.extractUniqueServices(workbench));
      wbServices.forEach(srv => {
        if (srv.key in allServices && srv.version in allServices[srv.key]) {
          return;
        }
        const idx = unaccessibleServices.findIndex(unSrv => unSrv.key === srv.key && unSrv.version === srv.version);
        if (idx === -1) {
          unaccessibleServices.push(srv);
        }
      });
      return unaccessibleServices;
    },

    getInaccessibleServicesMsg: function(inaccessibleServices, workbench) {
      let msg = qx.locale.Manager.tr("Some services are not accessible:<br>");
      Object.values(workbench).forEach(node => {
        const inaccessibleService = inaccessibleServices.find(srv => srv.key === node.key && srv.version === node.version);
        if (inaccessibleService) {
          const n = inaccessibleService.key.lastIndexOf("/");
          const friendlyKey = inaccessibleService.key.substring(n + 1);
          msg += `- ${node.label} (${friendlyKey}:${inaccessibleService.version})<br>`;
        }
      });
      return msg;
    },

    getFilePicker: function() {
      return this.getLatest("simcore/services/frontend/file-picker");
    },

    getParametersMetadata: function() {
      const parametersMetadata = [];
      const services = this.__servicesCached;
      for (const key in services) {
        if (key.includes("simcore/services/frontend/parameter/")) {
          const latest = this.getLatest(key);
          if (latest) {
            parametersMetadata.push(latest);
          }
        }
      }
      return parametersMetadata;
    },

    getParameterMetadata: function(type) {
      return this.getLatest("simcore/services/frontend/parameter/"+type);
    },

    getProbeMetadata: function(type) {
      return this.getLatest("simcore/services/frontend/iterator-consumer/probe/"+type);
    },

    __addToCache: function(service) {
      const key = service.key;
      const version = service.version;
      if (!(key in this.__servicesCached)) {
        this.__servicesCached[key] = {};
      }
      this.__servicesCached[key][version] = service;
    },

    __isInCache: function(key, version) {
      return (
        key in this.__servicesCached &&
        version in this.__servicesCached[key]
      );
    },

    __getLatestCached: function() {
      const latestServices = {};
      for (const key in this.__servicesCached) {
        let versions = Object.keys(this.__servicesCached[key]);
        versions = versions.sort(osparc.utils.Utils.compareVersionNumbers).reverse();
        const latest = this.__servicesCached[key][versions[0]];
        latestServices[key] = osparc.utils.Utils.deepCloneObject(latest);
      }
      return latestServices;
    },

    __addTSRInfo: function(service) {
      if (osparc.data.model.Node.isComputational(service)) {
        osparc.metadata.Quality.attachQualityToObject(service);
      }
    },

    __addTSRInfos: function(servicesObj) {
      Object.values(servicesObj).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          this.__addTSRInfo(service);
        });
      });
    },

    __addExtraTypeInfo: function(service) {
      service["xType"] = service["type"];
      if (["backend", "frontend"].includes(service["xType"])) {
        if (osparc.data.model.Node.isFilePicker(service)) {
          service["xType"] = "file";
        } else if (osparc.data.model.Node.isParameter(service)) {
          service["xType"] = "parameter";
        } else if (osparc.data.model.Node.isIterator(service)) {
          service["xType"] = "iterator";
        } else if (osparc.data.model.Node.isProbe(service)) {
          service["xType"] = "probe";
        }
      }
    },

    __addExtraTypeInfos: function(servicesObj) {
      Object.values(servicesObj).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          this.__addExtraTypeInfo(service);
        });
      });
    },

    __addHit: function(service, favServices) {
      const cachedHit = favServices ? favServices : osparc.utils.Utils.localCache.getFavServices();
      const found = Object.keys(cachedHit).find(favSrv => favSrv === service["key"]);
      service.hits = found ? cachedHit[found]["hits"] : 0;
    },

    __addHits: function(servicesObj) {
      const favServices = osparc.utils.Utils.localCache.getFavServices();
      Object.values(servicesObj).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          this.__addHit(service, favServices);
        });
      });
    },
  }
});
