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
    * @param portData {Object} port data
    * @param isInput {Boolean} whether the port is an input or output
  */
  construct: function(nodeId, portData, isInput) {
    this.base(arguments);

    this.set({
      nodeId,
      portKey: portData.keyId,
      label: portData.label || null,
      description: portData.description || null,
      type: portData.type || null,
      portIO: isInput ? "input" : "output",
    });

    const portDataCopy = osparc.utils.Utils.deepCloneObject(portData);
    // delete keys that are already set as properties...
    delete portDataCopy.keyId;
    delete portDataCopy.label;
    delete portDataCopy.description;
    delete portDataCopy.type;
    // ...extend the current object with the rest of the data
    Object.assign(this, portDataCopy);
  },

  statics: {
    FP_PORT_KEY: "outFile",
    PARAM_PORT_KEY: "out_1",
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

    type: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeType",
    },

    portIO: {
      check: ["input", "output"],
      init: null,
      nullable: false,
    },

    value: {
      nullable: true,
      init: null,
      event: "changeValue",
    },

    input: {
      check: "osparc.data.model.NodePort",
      nullable: true,
      init: null,
      event: "changeInput",
    },

    status: {
      check: [
        "UPLOAD_STARTED",                 // OutputStatus
        "UPLOAD_WAS_ABORTED",             // OutputStatus
        "UPLOAD_FINISHED_SUCCESSFULLY",   // OutputStatus
        "UPLOAD_FINISHED_WITH_ERROR",     // OutputStatus
        "DOWNLOAD_STARTED",               // InputStatus
        "DOWNLOAD_SUCCEEDED_EMPTY",       // InputStatus
        "DOWNLOAD_WAS_ABORTED",           // InputStatus
        "DOWNLOAD_FINISHED_SUCCESSFULLY", // InputStatus
        "DOWNLOAD_FINISHED_WITH_ERROR",   // InputStatus
      ],
      nullable: true,
      init: null,
      event: "changeStatus",
    },
  },
});
