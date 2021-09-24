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

    arePortsCompatible: function(node1, portId1, node2, portId2) {
      return osparc.data.Resources.getCompatibleInputs(node1, portId1, node2)
        .then(compatiblePorts => {
          let arePortsCompatible = compatiblePorts.includes(portId2);
          if (node2.isIteratorConsumer()) {
            arePortsCompatible = node1.hasIteratorUpstream();
          }
          return arePortsCompatible;
        });
    },

    isDataALink: function(data) {
      return (data !== null && typeof data === "object" && data.nodeUuid);
    },

    isDataAParameter: function(data) {
      return (data !== null && typeof data === "string" && data.startsWith("{{") && data.endsWith("}}"));
    },

    getPortType: function(portsMetadata, portId) {
      if (portId in portsMetadata) {
        return portsMetadata[portId]["type"];
      }
      return null;
    }
  }
});
