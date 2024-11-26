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

/**
 *   Collection of methods for dealing with services data type conversions, extract
 * specific information.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let latestSrv = osparc.service.Utils.getLatest(key);
 * </pre>
 */

qx.Class.define("osparc.service.Utils", {
  type: "static",

  statics: {
    TYPES: {
      parameter: {
        label: qx.locale.Manager.tr("Parameter"),
        icon: "@FontAwesome5Solid/sliders-h/",
        sorting: 0
      },
      file: {
        label: qx.locale.Manager.tr("File"),
        icon: "@FontAwesome5Solid/file/",
        sorting: 1
      },
      iterator: {
        label: qx.locale.Manager.tr("Iterator"),
        icon: "@FontAwesome5Solid/copy/",
        sorting: 2
      },
      computational: {
        label: qx.locale.Manager.tr("Computational"),
        icon: "@FontAwesome5Solid/cogs/",
        sorting: 3
      },
      dynamic: {
        label: qx.locale.Manager.tr("Interactive"),
        icon: "@FontAwesome5Solid/mouse-pointer/",
        sorting: 4
      },
      probe: {
        label: qx.locale.Manager.tr("Probe"),
        icon: "@FontAwesome5Solid/thermometer/",
        sorting: 5
      }
    },

    getTypes: function() {
      return Object.keys(this.TYPES);
    },

    getType: function(type) {
      return this.TYPES[type.trim().toLowerCase()];
    },

    getIcon: function(type) {
      const typeInfo = this.getType(type);
      if (typeInfo) {
        return typeInfo["icon"];
      }
      return null;
    },

    getSorting: function(type) {
      const typeInfo = this.getType(type);
      if (typeInfo) {
        return typeInfo["sorting"];
      }
      return 0;
    },

    sortObjectsBasedOn: function(servicesArray, basedOn) {
      if (basedOn === undefined) {
        basedOn = {
          "sort": "hits",
          "order": "down"
        };
      }
      servicesArray.sort((a, b) => {
        if (basedOn.sort === "hits") {
          if (a[basedOn.sort] !== b[basedOn.sort]) {
            if (basedOn.order === "down") {
              return b[basedOn.sort] - a[basedOn.sort];
            }
            return a[basedOn.sort] - b[basedOn.sort];
          }
          return a["name"].localeCompare(b["name"]);
        } else if (basedOn.sort === "name") {
          if (basedOn.order === "down") {
            return a["name"].localeCompare(b["name"]);
          }
          return b["name"].localeCompare(a["name"]);
        }
        return 0;
      });
    },

    convertArrayToObject: function(servicesArray) {
      let services = {};
      for (let i = 0; i < servicesArray.length; i++) {
        const service = servicesArray[i];
        if (!Object.prototype.hasOwnProperty.call(services, service.key)) {
          services[service.key] = {};
        }
        if (!Object.prototype.hasOwnProperty.call(services[service.key], service.version)) {
          services[service.key][service.version] = {};
        }
        services[service.key][service.version] = service;
      }
      return services;
    },

    getVersions: function(key, filterDeprecated = true) {
      const services = osparc.store.Services.servicesCached;
      let versions = [];
      if (key in services) {
        const serviceVersions = services[key];
        versions = versions.concat(Object.keys(serviceVersions));
        if (filterDeprecated) {
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
      const services = osparc.store.Services.servicesCached;
      if (key in services) {
        const versions = this.getVersions(key, true);
        if (versions.length) {
          return services[key][versions[0]];
        }
      }
      return null;
    },

    getLatestCompatible: function(key, version) {
      const services = osparc.store.Services.servicesCached;
      if (key in services && version in services[key]) {
        const serviceMD = services[key][version];
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
      const services = osparc.store.Services.servicesCached;
      if (key in services && version in services[key]) {
        return this.extractVersionDisplay(services[key][version]);
      }
      return null;
    },

    extractVersionDisplay: function(metadata) {
      return metadata["versionDisplay"] ? metadata["versionDisplay"] : metadata["version"];
    },

    getReleasedDate: function(key, version) {
      const services = osparc.store.Services.servicesCached;
      if (
        key in services &&
        version in services[key] &&
        "released" in services[key][version]
      ) {
        return services[key][version]["released"];
      }
      return null;
    },

    versionToListItem: function(key, version) {
      const versionDisplay = this.getVersionDisplay(key, version);
      const listItem = new qx.ui.form.ListItem(versionDisplay);
      listItem.version = version;
      return listItem;
    },

    canIWrite: function(serviceAccessRights) {
      const groupsStore = osparc.store.Groups.getInstance();
      const orgIDs = groupsStore.getOrganizationIds();
      orgIDs.push(groupsStore.getMyGroupId());
      return osparc.share.CollaboratorsService.canGroupsWrite(serviceAccessRights, orgIDs);
    },

    DEPRECATED_SERVICE_TEXT: qx.locale.Manager.tr("Service deprecated"),
    DEPRECATED_DYNAMIC_INSTRUCTIONS: qx.locale.Manager.tr("Please go back to the dashboard and Update the Service or download its data and upload it to an updated version"),
    DEPRECATED_COMPUTATIONAL_INSTRUCTIONS: qx.locale.Manager.tr("Please instantiate an updated version"),
    RETIRED_SERVICE_TEXT: qx.locale.Manager.tr("Service retired"),
    RETIRED_DYNAMIC_INSTRUCTIONS: qx.locale.Manager.tr("Please download the Service data and upload it to an updated version"),
    RETIRED_COMPUTATIONAL_INSTRUCTIONS: qx.locale.Manager.tr("Please instantiate an updated version"),
    DEPRECATED_AUTOUPDATABLE_INSTRUCTIONS: qx.locale.Manager.tr("Please Stop the Service and then Update it"),
    RETIRED_AUTOUPDATABLE_INSTRUCTIONS: qx.locale.Manager.tr("Please Update the Service"),

    isUpdatable: function(metadata) {
      const latestCompatible = this.getLatestCompatible(metadata["key"], metadata["version"]);
      return latestCompatible && (metadata["key"] !== latestCompatible["key"] || metadata["version"] !== latestCompatible["version"]);
    },

    isDeprecated: function(metadata) {
      if (metadata && "deprecated" in metadata && ![null, undefined].includes(metadata["deprecated"])) {
        const deprecationTime = new Date(metadata["deprecated"]);
        const now = new Date();
        return deprecationTime.getTime() > now.getTime();
      }
      return false;
    },

    isRetired: function(metadata) {
      if (metadata && "deprecated" in metadata && ![null, undefined].includes(metadata["deprecated"])) {
        const deprecationTime = new Date(metadata["deprecated"]);
        const now = new Date();
        return deprecationTime.getTime() < now.getTime();
      }
      return false;
    },

    getDeprecationDateText: function(metadata) {
      const deprecationTime = new Date(metadata["deprecated"]);
      return qx.locale.Manager.tr("It will be Retired: ") + osparc.utils.Utils.formatDate(deprecationTime);
    },

    getFilePicker: function() {
      return this.self().getLatest("simcore/services/frontend/file-picker");
    },

    getParametersMetadata: function() {
      const parametersMetadata = [];
      const services = osparc.store.Services.servicesCached;
      for (const key in services) {
        if (key.includes("simcore/services/frontend/parameter/")) {
          const latest = this.self().getLatest(key);
          if (latest) {
            parametersMetadata.push(latest);
          }
        }
      }
      return parametersMetadata;
    },

    getParameterMetadata: function(type) {
      return this.self().getLatest("simcore/services/frontend/parameter/"+type);
    },

    getProbeMetadata: function(type) {
      return this.self().getLatest("simcore/services/frontend/iterator-consumer/probe/"+type);
    },

    removeFileToKeyMap: function(service) {
      [
        "inputs",
        "outputs"
      ].forEach(inOut => {
        if (inOut in service) {
          for (const key in service[inOut]) {
            if ("fileToKeyMap" in service[inOut][key]) {
              delete service[inOut][key]["fileToKeyMap"];
            }
          }
        }
      });
    },

    getUniqueServicesFromWorkbench: function(workbench) {
      const services = [];
      Object.values(workbench).forEach(node => {
        const service = {
          key: node["key"],
          version: node["version"]
        };
        const idx = services.findIndex(existingSrv => existingSrv.key === service.key && existingSrv.version === service.version);
        if (idx === -1) {
          services.push(service);
        }
      });
      return services;
    }
  }
});
