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
 * Class that stores Function data.
 */

qx.Class.define("osparc.data.model.Function", {
  extend: qx.core.Object,

  /**
   * @param functionData {Object} Object containing the serialized Function Data
   */
  construct: function(functionData) {
    this.base(arguments);

    this.set({
      uuid: functionData.uuid,
      functionType: functionData.functionClass,
      name: functionData.name,
      description: functionData.description,
      inputSchema: functionData.inputSchema || this.getInputSchema(),
      outputSchema: functionData.outputSchema || this.getOutputSchema(),
      defaultInputs: functionData.defaultInputs || this.getDefaultInputs(),
      accessRights: functionData.accessRights || this.getAccessRights(),
      creationDate: functionData.creationDate ? new Date(functionData.creationDate) : this.getCreationDate(),
      lastChangeDate: functionData.lastChangeDate ? new Date(functionData.lastChangeDate) : this.getLastChangeDate(),
      thumbnail: functionData.thumbnail || this.getThumbnail(),
    });

    const wbData = functionData.workbench || {};
    const wbUiData = functionData.ui || {};
    const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview2(wbData, wbUiData);
    this.setWorkbenchUiPreview(workbenchUIPreview);
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      event: "changeUuid",
      init: ""
    },

    functionType: {
      check: ["PROJECT"],
      nullable: false,
      event: "changeFunctionType",
      init: null
    },

    name: {
      check: "String",
      nullable: false,
      event: "changeName",
      init: "New Study"
    },

    description: {
      check: "String",
      nullable: true,
      event: "changeDescription",
      init: null
    },

    inputSchema: {
      check: "Object",
      nullable: false,
      event: "changeInputSchema",
      init: {}
    },

    outputSchema: {
      check: "Object",
      nullable: false,
      event: "changeOutputSchema",
      init: {}
    },

    defaultInputs: {
      check: "Object",
      nullable: false,
      event: "changeDefaultInputs",
      init: {}
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
      init: {}
    },

    creationDate: {
      check: "Date",
      nullable: false,
      event: "changeCreationDate",
      init: new Date()
    },

    lastChangeDate: {
      check: "Date",
      nullable: false,
      event: "changeLastChangeDate",
      init: new Date()
    },

    thumbnail: {
      check: "String",
      nullable: true,
      event: "changeThumbnail",
      init: null
    },

    workbenchUiPreview: {
      check: "osparc.workbench.WorkbenchUIPreview2",
      nullable: false,
      init: null,
    },
  },

  statics: {
    canIWrite: function(accessRights) {
      const groupsStore = osparc.store.Groups.getInstance();
      const gIds = groupsStore.getOrganizationIds();
      gIds.push(groupsStore.getMyGroupId());
      let canWrite = false;
      for (let i=0; i<gIds.length && !canWrite; i++) {
        const gid = gIds[i];
        canWrite = (gid in accessRights) ? accessRights[gid]["write"] : false;
      }
      return canWrite;
    },
  }
});
