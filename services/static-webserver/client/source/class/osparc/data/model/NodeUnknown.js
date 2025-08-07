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

/**
 * Class that stores Node data without a known metadata.
 */

qx.Class.define("osparc.data.model.NodeUnknown", {
  extend: osparc.data.model.Node,

  /**
    * @param study {osparc.data.model.Study} Study or Serialized Study Object
    * @param key {String} service's key
    * @param version {String} service's version
    * @param nodeId {String} uuid of the service represented by the node (not needed for new Nodes)
    */
  construct: function(study, key, version, nodeId) {
    const metadata = osparc.store.Services.getUnknownServiceMetadata();

    this.base(arguments, study, metadata, nodeId);
  },

  members: {
  }
});
