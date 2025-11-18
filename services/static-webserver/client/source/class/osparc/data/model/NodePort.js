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
 * Class that stores Node Port data.
 */

qx.Class.define("osparc.data.model.NodePort", {
  extend: qx.core.Object,

  /**
    * @param nodeId {String} uuid of the service represented by the node (not needed for new Nodes)
    * @param portKey {String} unique key of the port represented by the node
    * @param isInput {Boolean} whether the port is an input or output
  */
  construct: function(nodeId, portKey, isInput) {
    this.base(arguments);

    this.set({
      nodeId: nodeId || osparc.utils.Utils.uuidV4(),
      portKey,
      portType: isInput ? "input" : "output",
    });
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: false,
    },

    portType: {
      check: ["input", "output"],
      init: null,
      nullable: false,
    },

    label: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeLabel",
    },

    description: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeDescription",
    },

    status: {
      check: [
        "UPLOAD_STARTED",                 // OutputStatus
        "UPLOAD_WAS_ABORTED",             // OutputStatus
        "UPLOAD_FINISHED_SUCCESSFULLY",   // OutputStatus
        "UPLOAD_FINISHED_WITH_ERROR",     // OutputStatus
        "DOWNLOAD_STARTED",               // InputStatus
        "DOWNLOAD_WAS_ABORTED",           // InputStatus
        "DOWNLOAD_FINISHED_SUCCESSFULLY", // InputStatus
        "DOWNLOAD_FINISHED_WITH_ERROR",   // InputStatus
      ],
      nullable: true,
      init: null,
      event: "changeStatus",
    },

    connected: {
      check: "Boolean",
      init: false,
      event: "changeConnected",
    },

    input: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeInput"
    },
  },
});
