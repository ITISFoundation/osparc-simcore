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
    __servicesPromisesCached: {},
    __studyServicesPromisesCached: {},

    getServicesLatest: function(useCache = true) {
      return new Promise(resolve => {
        if (useCache && Object.keys(this.__servicesCached)) {
          // return latest only
          const latest = this.__getLatestCached();
          resolve(latest);
          return;
        }

        osparc.data.Resources.getInstance().getAllPages("services")
          .then(servicesArray => {
            const servicesObj = osparc.service.Utils.convertArrayToObject(servicesArray);
            this.__addHits(servicesObj);
            this.__addTSRInfos(servicesObj);
            this.__addXTypeInfos(servicesObj);

            Object.values(servicesObj).forEach(serviceKey => {
              Object.values(serviceKey).forEach(service => this.__addServiceToCache(service));
            });

            resolve(servicesObj);
          })
          .catch(err => osparc.FlashMessenger.logError(err, qx.locale.Manager.tr("Unable to fetch Services")));
      });
    },

    getLatest: function(key) {
      const services = this.__servicesCached;
      if (key in services) {
        const latestMetadata = Object.values(services[key])[0];
        if (!osparc.service.Utils.isDeprecated(latestMetadata)) {
          return latestMetadata;
        }
      }
      return null;
    },

    getLatestCompatible: function(key, version) {
      const services = this.__servicesCached;
      if (key in services && version in services[key]) {
        const historyEntry = osparc.service.Utils.extractVersionFromHistory(services[key][version]);
        if (historyEntry["compatibility"] && historyEntry["compatibility"]["canUpdateTo"]) {
          const canUpdateTo = historyEntry["compatibility"]["canUpdateTo"];
          return {
            key: "key" in canUpdateTo ? canUpdateTo["key"] : key, // key is optional
            version: canUpdateTo["version"]
          };
        }
        // the provided key/version itself is the latest compatible
        return {
          key,
          version
        };
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
      // avoid request deduplication
      if (key in this.__servicesPromisesCached && version in this.__servicesPromisesCached[key]) {
        return this.__servicesPromisesCached[key][version];
      }

      // Create a new promise
      const promise = new Promise((resolve, reject) => {
        if (
          useCache &&
          this.__isInCache(key, version) &&
          (
            this.__servicesCached[key][version] === null ||
            "history" in this.__servicesCached[key][version]
          )
        ) {
          resolve(this.__servicesCached[key][version]);
          return;
        }

        if (!(key in this.__servicesPromisesCached)) {
          this.__servicesPromisesCached[key] = {};
        }
        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        this.__servicesPromisesCached[key][version] = osparc.data.Resources.fetch("services", "getOne", params)
          .then(service => {
            this.__addServiceToCache(service);
            // Resolve the promise locally before deleting it
            resolve(service);
          })
          .catch(err => {
            // Store null in cache to avoid repeated failed requests
            this.__addToCache(key, version, null);
            console.error(err);
            reject(err);
          })
          .finally(() => {
            // Remove the promise from the cache
            delete this.__servicesPromisesCached[key][version];
          });
      });

      //  Store the promise in the cache
      //  The point of keeping this assignment outside of the main Promise block is to
      // ensure that the promise is immediately stored in the cache before any asynchronous
      // operations (like fetch) are executed. This prevents duplicate requests for the
      // same key and version when multiple consumers call getService concurrently.
      this.__servicesPromisesCached[key][version] = promise;
      return promise;
    },

    getStudyServices: function(studyId) {
      // avoid request deduplication
      if (studyId in this.__studyServicesPromisesCached) {
        return this.__studyServicesPromisesCached[studyId];
      }

      const params = {
        url: {
          studyId
        }
      };
      this.__studyServicesPromisesCached[studyId] = osparc.data.Resources.fetch("studies", "getServices", params)
        .then(resp => {
          const services = resp["services"];
          services.forEach(service => {
            // this service information is not complete, keep it in cache anyway
            service.version = service["release"]["version"];
            this.__addServiceToCache(service);
          });
          return resp;
        })
        .finally(() => {
          delete this.__studyServicesPromisesCached[studyId];
        });

      return this.__studyServicesPromisesCached[studyId]
    },

    __getAllVersions: function(key) {
      const services = this.__servicesCached;
      let versions = [];
      if (key in services) {
        const serviceVersions = services[key];
        versions = versions.concat(Object.keys(serviceVersions));
        versions.sort(osparc.utils.Utils.compareVersionNumbers);
      }
      return versions.reverse();
    },

    populateVersionsSelectBox: function(key, selectBox) {
      const versions = this.__getAllVersions(key);
      return this.getService(key, versions[0])
        .then(latestMetadata => {
          latestMetadata["history"].forEach(historyEntry => {
            if (!historyEntry["retired"]) {
              const versionDisplay = osparc.service.Utils.extractVersionDisplay(historyEntry);
              const listItem = new qx.ui.form.ListItem(versionDisplay);
              osparc.utils.Utils.setIdToWidget(listItem, "serviceVersionItem_" + versionDisplay);
              listItem.version = historyEntry["version"];
              selectBox.add(listItem);
            }
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
              if (excludeDeprecated) {
                if (
                  osparc.service.Utils.isRetired(serviceLatest) ||
                  osparc.service.Utils.isDeprecated(serviceLatest)
                ) {
                  // first check if a previous version of this service isn't deprecated
                  // getService to get its history
                  await this.getService(serviceLatest["key"], serviceLatest["version"]);
                  const serviceMetadata = this.__servicesCached[key][serviceLatest["version"]];
                  for (let j=0; j<serviceMetadata["history"].length; j++) {
                    const historyEntry = serviceMetadata["history"][j];
                    if (!historyEntry["retired"]) {
                      // one older non retired version found
                      let olderNonRetired = await this.getService(key, historyEntry["version"]);
                      if (!olderNonRetired) {
                        olderNonRetired = await this.getService(key, historyEntry["version"]);
                      }
                      serviceLatest = osparc.utils.Utils.deepCloneObject(olderNonRetired);
                      // make service metadata latest model like
                      serviceLatest["release"] = osparc.service.Utils.extractVersionFromHistory(olderNonRetired);
                      break;
                    }
                  }
                }
                if (
                  osparc.service.Utils.isRetired(serviceLatest) ||
                  osparc.service.Utils.isDeprecated(serviceLatest)
                ) {
                  // do not add retired services
                  continue;
                }
              }
              servicesList.push(serviceLatest);
            }
          })
          .catch(err => console.error(err))
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
      return osparc.data.Resources.fetch("services", "patch", params)
        .then(() => {
          this.__servicesCached[key][version][fieldKey] = value;
          serviceData[fieldKey] = value;
        });
    },

    getStudyServicesMetadata: function(studyData) {
      const wbServices = osparc.study.Utils.extractUniqueServices(studyData["workbench"]);
      const promises = [];
      wbServices.forEach(srv => {
        promises.push(this.getService(srv["key"], srv["version"]));
      });
      return Promise.allSettled(promises);
    },

    getInaccessibleServices: function(workbench) {
      const allServices = this.__servicesCached;
      const inaccessibleServices = [];
      const wbServices = osparc.study.Utils.extractUniqueServices(workbench);
      wbServices.forEach(srv => {
        if (
          srv.key in allServices &&
          srv.version in allServices[srv.key] &&
          allServices[srv.key][srv.version] // check metadata is not null
        ) {
          return;
        }
        const idx = inaccessibleServices.findIndex(unSrv => unSrv.key === srv.key && unSrv.version === srv.version);
        if (idx === -1) {
          inaccessibleServices.push(srv);
        }
      });
      return inaccessibleServices;
    },

    getInaccessibleServicesMsg: function(inaccessibleServices, workbench) {
      let msg = qx.locale.Manager.tr("Some services are inaccessible:<br>");
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

    __addServiceToCache: function(service) {
      this.__addHit(service);
      this.__addTSRInfo(service);
      this.__addXTypeInfo(service);

      const key = service.key;
      const version = service.version;
      service["resourceType"] = "service";
      this.__addToCache(key, version, service);
    },

    __addToCache: function(key, version, value) {
      if (!(key in this.__servicesCached)) {
        this.__servicesCached[key] = {};
      }
      // some services that go to the cache are not complete, e.g. study services
      // if the one in the cache is the complete one, do not overwrite it
      if (
        key in this.__servicesCached[key] &&
        version in this.__servicesCached[key] &&
        this.__servicesCached[key][version]["inputs"]
      ) {
        return;
      }
      this.__servicesCached[key][version] = value;
    },

    __isInCache: function(key, version) {
      return (
        this.__servicesCached &&
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

    __addXTypeInfo: function(service) {
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

    __addXTypeInfos: function(servicesObj) {
      Object.values(servicesObj).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          this.__addXTypeInfo(service);
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
