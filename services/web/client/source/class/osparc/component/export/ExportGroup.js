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

    this.set({
      inputNode: node
    });

    this.__cloneInput();

    this.__buildLayout();
  },

  events: {
    "finished": "qx.event.type.Data"
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
    __groupName: null,
    __groupDesc: null,

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
        this.__exportAsMacroService();
      }, this);
      this._add(exportBtn);
    },

    __buildMetaDataForm: function() {
      const metaDataForm = new qx.ui.form.Form();

      const groupName = this.__groupName = new qx.ui.form.TextField(this.getInputNode().getLabel());
      groupName.setRequired(true);
      metaDataForm.add(groupName, this.tr("Name"));

      const groupDesc = this.__groupDesc = new qx.ui.form.TextField();
      metaDataForm.add(groupDesc, this.tr("Description"));

      const formRenderer = new qx.ui.form.renderer.Single(metaDataForm).set({
        padding: 10
      });
      return formRenderer;
    },

    __cloneInput: function() {
      const inputNode = this.getInputNode();
      const key = inputNode.getKey();
      const version = inputNode.getVersion();
      const outputNode = new osparc.data.model.Node(key, version);
      this.setOutputNode(outputNode);

      const nodeData = inputNode.serialize();
      outputNode.setInputData(nodeData);
      outputNode.setOutputData(nodeData);
      outputNode.addInputNodes(nodeData.inputNodes);
      outputNode.addOutputNodes(nodeData.outputNodes);
    },

    __buildInputSettings: function() {
    },

    __buildExposedSettings: function() {
    },

    __exportAsMacroService: function() {
      const nodesGroup = this.getInputNode();
      const outputNode = this.getOutputNode();
      const workbench = this.__groupToWorkbenchData(nodesGroup);

      const nodeKey = "simcore/services/frontend/nodes-group/macros/" + nodesGroup.getNodeId();
      const version = "1.0.0";
      const nodesGroupService = osparc.utils.Services.getNodesGroupService();
      nodesGroupService["key"] = nodeKey;
      nodesGroupService["version"] = version;
      nodesGroupService["name"] = this.__groupName.getValue();
      nodesGroupService["description"] = this.__groupDesc.getValue();
      nodesGroupService["contact"] = osparc.auth.Data.getInstance().getEmail();
      nodesGroupService["workbench"] = workbench;

      const service = {};
      service[nodeKey] = {};
      service[nodeKey][version] = nodesGroupService;
      osparc.utils.Services.addServiceToCache(service);

      this.fireDataEvent("finished");
    },

    __groupToWorkbenchData: function(nodesGroup) {
      let workbench = {};

      // serialize innerNodes
      const innerNodes = nodesGroup.getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        workbench[innerNode.getNodeId()] = innerNode.serialize();
      });

      // remove parent from first level
      const firstLevelNodes = nodesGroup.getInnerNodes(false);
      Object.values(firstLevelNodes).forEach(firstLevelNode => {
        workbench[firstLevelNode.getNodeId()]["parent"] = null;
      });

      // deep copy workbench
      workbench = osparc.utils.Utils.deepCloneObject(workbench);

      // removeOutReferences
      workbench = this.__removeOutReferences(workbench);

      // replace Uuids
      workbench = osparc.data.Converters.replaceUuids(workbench);

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
    }
  }
});
