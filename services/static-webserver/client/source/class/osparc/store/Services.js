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
    servicesCached: {},

    getServicesLatest: function(useCache = true) {
      return new Promise(resolve => {
        if (useCache && Object.keys(this.servicesCached)) {
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

            // use response to populate servicesCached
            Object.values(servicesObj).forEach(serviceKey => {
              Object.values(serviceKey).forEach(srv => this.__addToCache(srv));
            });

            resolve(servicesObj);
          })
          .catch(err => console.error("getServices failed", err));
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
                return;
              }
              if (excludeDeprecated && serviceLatest["retired"]) {
                // first check if a previous version of this service isn't retired
                let versions = Object.keys(this.servicesCached[key]);
                versions = versions.sort(osparc.utils.Utils.compareVersionNumbers).reverse();
                for (let j=0; j<versions.length; j++) {
                  const version = versions[j];
                  if (!this.servicesCached[key][version]["retired"]) {
                    serviceLatest = await this.getService(key, version);
                    break;
                  }
                }
                if (serviceLatest["retired"]) {
                  // do not add retired services
                  return;
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

    getService: function(key, version, useCache = true) {
      return new Promise(resolve => {
        if (useCache && this.__isInCache(key, version)) {
          resolve(this.servicesCached[key][version]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.getOne("servicesV2", params)
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

    getResources: function(key, version) {
      return new Promise(resolve => {
        if (
          this.__isInCache(key, version) &&
          "resources" in this.servicesCached[key][version]
        ) {
          resolve(this.servicesCached[key][version]["resources"]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.get("serviceResources", params)
          .then(resources => {
            this.servicesCached[key][version]["resources"] = resources;
            resolve(resources);
          });
      });
    },

    getMetadata: function(key, version) {
      if (this.__isInCache(key, version)) {
        return this.servicesCached[key][version];
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
          this.servicesCached[key][version][fieldKey] = value;
          serviceData[fieldKey] = value;
        });
    },

    __addToCache: function(service) {
      const key = service.key;
      const version = service.version;
      if (!(key in this.servicesCached)) {
        this.servicesCached[key] = {};
      }
      this.servicesCached[key][version] = service;
      this.servicesCached[key][version]["cached"] = true;

      if ("history" in service) {
        service["history"].forEach(historyEntry => {
          const hVersion = historyEntry.version;
          if (!(hVersion in this.servicesCached[key])) {
            this.servicesCached[key][hVersion] = {};
            this.servicesCached[key][hVersion]["cached"] = false;
          }
          // merge history data into current metadata
          this.servicesCached[key][hVersion] = {
            ...this.servicesCached[key][hVersion],
            ...historyEntry
          };
        });
      }
    },

    __isInCache: function(key, version) {
      return (
        key in this.servicesCached &&
        version in this.servicesCached[key] &&
        this.servicesCached[key][version]["cached"]
      );
    },

    __getLatestCached: function() {
      const latestServices = {};
      for (const key in this.servicesCached) {
        let versions = Object.keys(this.servicesCached[key]);
        versions = versions.sort(osparc.utils.Utils.compareVersionNumbers).reverse();
        const latest = this.servicesCached[key][versions[0]];
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
