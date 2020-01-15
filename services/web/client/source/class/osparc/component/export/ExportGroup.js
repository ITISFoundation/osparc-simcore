/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 *
 */

qx.Class.define("osparc.component.export.ExportGroup", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    const key = "simcore/macros/" + osparc.utils.Utils.uuidv4();
    const version = "1.0.0";

    this.set({
      inputNode: node,
      outputNode: new osparc.data.model.Node(key, version)
    });

    this.__buildLayout();
  },

  properties: {
    inputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    outputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    }
  },

  members: {
    __buildLayout: function() {
      const formRenderer = this.__buildMetaDataForm();
      this._add(formRenderer);

      const scroll = new qx.ui.container.Scroll();
      const settingsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      this.__buildInputSettings();
      this.__buildExposedSettings();
      scroll.add(settingsLayout);
      this._add(scroll, {
        flex: 1
      });

      const exportBtn = new qx.ui.form.Button(this.tr("Export")).set({
        allowGrowX: false,
        alignX: "right"
      });
      exportBtn.addListener("execute", () => {
        this.__exportNode();
      }, this);
      this._add(exportBtn);
    },

    __buildMetaDataForm: function() {
      const metaDataForm = new qx.ui.form.Form();

      const serviceName = new qx.ui.form.TextField(this.getInputNode().getLabel());
      serviceName.setRequired(true);
      metaDataForm.add(serviceName, this.tr("Name"));

      const serviceDesc = new qx.ui.form.TextField();
      metaDataForm.add(serviceDesc, this.tr("Description"));

      const formRenderer = new qx.ui.form.renderer.Single(metaDataForm).set({
        padding: 10
      });
      return formRenderer;
    },

    __buildInputSettings: function() {
    },

    __buildExposedSettings: function() {
    },

    __exportNode: function() {
      const groupNode = this.getInputNode();
      let workbench = {};
      workbench = this.__serializeInputNode(groupNode, workbench);
      workbench = this.__serializeInnerNodes(groupNode, workbench);
      workbench = JSON.parse(JSON.stringify(workbench));
      workbench = this.__removeParentDependencies(groupNode, workbench);
      workbench = this.__removeOutReferences(workbench);
      workbench = this.__replaceUuids(workbench);
      console.log(workbench);
    },

    __serializeInputNode: function(groupNode, workbench) {
      workbench[groupNode.getNodeId()] = groupNode.serialize();
      return workbench;
    },

    __serializeInnerNodes: function(groupNode, workbench) {
      const allInnerNodes = groupNode.getInnerNodes(true);
      for (const innerNodeId in allInnerNodes) {
        const innerNode = allInnerNodes[innerNodeId];
        workbench[innerNode.getNodeId()] = innerNode.serialize();
      }
      return workbench;
    },

    __removeParentDependencies: function(groupNode, workbench) {
      const groupNodeId = groupNode.getNodeId();
      if ("parent" in workbench[groupNodeId]) {
        delete workbench[groupNodeId]["parent"];
      }
      if ("outputNode" in workbench[groupNodeId]) {
        workbench[groupNodeId]["outputNode"] = false;
      }
      return workbench;
    },

    __removeOutReferences: function(workbench) {
      const innerNodeIds = Object.keys(workbench);
      for (const nodeId in workbench) {
        const node = workbench[nodeId];
        const inputNodes = node.inputNodes;
        for (let i=0; i<inputNodes.length; i++) {
          if (innerNodeIds.indexOf(inputNodes[i]) === -1) {
            // remove node connection
            inputNodes.splice(i, 1);

            // remove port connections
            const inputs = node.inputs;
            for (const portId in inputs) {
              const input = inputs[portId];
              if (input instanceof Object && "nodeUuid" in input && innerNodeIds.indexOf(input["nodeUuid"]) === -1) {
                delete inputs[portId];
              }
            }
          }
        }
      }
      return workbench;
    },

    __replaceUuids: function(workbench) {
      let workbenchStr = JSON.stringify(workbench);
      const innerNodeIds = Object.keys(workbench);
      for (let i=0; i<innerNodeIds.length; i++) {
        const innerNodeId = innerNodeIds[i];
        const newNodeId = osparc.utils.Utils.uuidv4();
        // workbenchStr = workbenchStr.replace(innerNodeId, newNodeId);
        const re = new RegExp(innerNodeId, "g");
        workbenchStr = workbenchStr.replace(re, newNodeId); // Using regex for replacing ALL matches
      }
      workbench = JSON.parse(workbenchStr);
      return workbench;
    }
  }
});
