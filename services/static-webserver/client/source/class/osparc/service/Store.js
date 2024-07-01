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

qx.Class.define("osparc.service.Store", {
  type: "static",

  statics: {
    servicesCached: {},

    getServicesLatest: function(useCache = true) {
      return new Promise(resolve => {
        if (useCache && Object.keys(this.servicesCached)) {
          // give latest only
          const latest = this.__getLatestCached();
          resolve(latest);
          return;
        }

        osparc.data.Resources.get("servicesDev")
          .then(servicesArray => {
            osparc.service.Utils.addHits(servicesArray);
            const servicesObj = osparc.service.Utils.convertArrayToObject(servicesArray);
            osparc.service.Utils.addTSRInfos(servicesObj);
            osparc.service.Utils.addExtraTypeInfos(servicesObj);

            // use response to populate servicesCached
            Object.values(servicesObj).forEach(serviceKey => {
              Object.values(serviceKey).forEach(srv => this.__addToCache(srv));
            });

            resolve(servicesObj);
          })
          .catch(err => console.error("getServices failed", err));
      });
    },

    getService: function(key, version, useCache = true) {
      return new Promise(resolve => {
        if (useCache && this.__isInCache()) {
          resolve(this.servicesCached[key][version]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.getOne("servicesDev", params)
          .then(service => {
            osparc.service.Utils.addHit(service);
            osparc.service.Utils.addTSRInfo(service);
            osparc.service.Utils.addExtraTypeInfo(service);
            this.__addToCache(service)
            resolve(service);
          });
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
    }
  }
});
