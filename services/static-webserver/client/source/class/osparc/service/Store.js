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

    getServicesLatest: function(useCache = true, includeRetired = true) {
      return new Promise(resolve => {
        if (useCache) {
          resolve(this.servicesCached);
          return;
        }

        let allServices = [];
        osparc.data.Resources.get("servicesDev")
          .then(services => {
            allServices = services;
          })
          .catch(err => console.error("getServices failed", err))
          .finally(() => {
            let servicesObj = {};
            if (includeRetired) {
              servicesObj = osparc.service.Utils.convertArrayToObject(allServices);
            } else {
              const nonDepServices = allServices.filter(service => !(osparc.service.Utils.isRetired(service) || osparc.service.Utils.isDeprecated(service)));
              servicesObj = osparc.service.Utils.convertArrayToObject(nonDepServices);
            }
            osparc.service.Utils.addTSRInfo(servicesObj);
            osparc.service.Utils.addExtraTypeInfo(servicesObj);
            if (includeRetired) {
              osparc.service.Utils.servicesCached = servicesObj;
            }
            resolve(servicesObj);
          });
      });
    },

    getService: function(key, version, useCache = true) {
      return new Promise(resolve => {
        if (useCache && key in this.servicesCached && version in this.servicesCached[key]) {
          resolve(this.servicesCached[key][version]);
          return;
        }

        const params = {
          url: osparc.data.Resources.getServiceUrl(key, version)
        };
        osparc.data.Resources.getOne("servicesDev", params)
          .then(serviceData => {
            resolve(serviceData);
          });
      });
    }
  }
});
