/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for dealing with ports.
 *
 */

qx.Class.define("osparc.utils.Ports", {
  type: "static",

  statics: {
    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = osparc.data.MimeType.getMimeType(typeA);
      let mtB = osparc.data.MimeType.getMimeType(typeB);
      return mtA && mtB &&
        new osparc.data.MimeType(mtA).match(new osparc.data.MimeType(mtB));
    },

    arePortsCompatible: function(port1, port2) {
      return new Promise(resolve => {
        const ms = Math.random() * 1000;
        setTimeout(() => {
          const compatible = port1.type && port2.type && this.__matchPortType(port1.type, port2.type);
          resolve(compatible);
        }, ms);
      });
    },

    getCompatiblePorts: function(node1, port1, node2) {
      const params = {
        url: {
          "serviceKey2": encodeURIComponent(node2.getKey()),
          "serviceVersion2": node2.getVersion(),
          "serviceKey1": encodeURIComponent(node1.getKey()),
          "serviceVersion1": node1.getVersion(),
          "portKey1": port1
        }
      };
      // return osparc.data.Resources.fetch("services", "matchInputs", params);
      osparc.data.Resources.fetch("services", "matchInputs", params);
      return new Promise(resolve => {
        const ms = 2000;
        setTimeout(() => {
          const compatiblePorts = ["input_1"];
          resolve(compatiblePorts);
        }, ms);
      });
    },

    isDataALink: function(data) {
      return (data !== null && typeof data === "object" && data.nodeUuid);
    },

    isDataAParameter: function(data) {
      return (data !== null && typeof data === "string" && data.startsWith("{{") && data.endsWith("}}"));
    }
  }
});
