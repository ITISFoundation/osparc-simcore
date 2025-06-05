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
    arePortsCompatible: function(node1, portId1, node2, portId2) {
      return osparc.data.Resources.getInstance().getCompatibleInputs(node1, portId1, node2)
        .then(compatiblePorts => compatiblePorts.includes(portId2));
    },

    isDataALink: function(data) {
      return (data !== null && typeof data === "object" && data.nodeUuid);
    },

    isDataAParameter: function(data) {
      return (data !== null && typeof data === "string" && data.startsWith("{{") && data.endsWith("}}"));
    },

    getPortType: function(portsMetadata, portId) {
      let portType = null;
      if (portId in portsMetadata) {
        portType = portsMetadata[portId]["type"];
        if (portType === "ref_contentSchema" && "contentSchema" in portsMetadata[portId]) {
          portType = portsMetadata[portId]["contentSchema"]["type"];
        }
      }
      return portType;
    }
  }
});
