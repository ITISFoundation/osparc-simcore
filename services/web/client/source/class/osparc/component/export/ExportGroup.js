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

    this.__prepareOutputNode();
    this.__prepareOutputWorkbench();
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
    },

    outputWorkbench: {
      check: "osparc.data.model.Workbench",
      nullable: false
    }
  },

  members: {
    __groupName: null,
    __groupDesc: null,
    __activeStudy: null,

    tearDown: function() {
      osparc.store.Store.getInstance().setCurrentStudy(this.__activeStudy);
    },

    __prepareOutputNode: function() {
      const inputNode = this.getInputNode();

      const key = inputNode.getKey();
      const version = inputNode.getVersion();
      const nodeData = inputNode.serialize();
      const nodesGroup = new osparc.data.model.Node(key, version);
      nodesGroup.populateInputOutputData(nodeData);
      this.setOutputNode(nodesGroup);
    },

    __prepareOutputWorkbench: function() {
      const inputNode = this.getInputNode();

      const studydata = {
        workbench: this.__groupToWorkbenchData(inputNode)
      };
      const dummyStudy = new osparc.data.model.Study(studydata);

      this.__activeStudy = osparc.store.Store.getInstance().getCurrentStudy();
      osparc.store.Store.getInstance().setCurrentStudy(dummyStudy);
      this.setOutputWorkbench(dummyStudy.getWorkbench());
      dummyStudy.getWorkbench().buildWorkbench();
    },

    __buildLayout: function() {
      const formRenderer = this.__buildMetaDataForm();
      this._add(formRenderer);

      const scroll = new qx.ui.container.Scroll();
      const settingsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const settingsView = this.__buildOutputSettings();
      settingsLayout.add(settingsView, {
        flex: 1
      });
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

    __buildOutputSettings: function() {
      const innerNodes = this.getOutputWorkbench().getNodes(true);
      const settingsEditorLayout = osparc.component.node.GroupNodeView.getSettingsEditorLayout(innerNodes);
      return settingsEditorLayout;
    },

    __exportAsMacroService: function() {
      const outputNode = this.getOutputNode();
      const outputWorkbench = this.getOutputWorkbench();

      const nodeKey = "simcore/services/frontend/nodes-group/macros/" + outputNode.getNodeId();
      const version = "1.0.0";
      const nodesGroupService = osparc.utils.Services.getNodesGroup();
      nodesGroupService["key"] = nodeKey;
      nodesGroupService["version"] = version;
      nodesGroupService["name"] = this.__groupName.getValue();
      nodesGroupService["description"] = this.__groupDesc.getValue();
      nodesGroupService["contact"] = osparc.auth.Data.getInstance().getEmail();
      nodesGroupService["workbench"] = outputWorkbench.serializeWorkbench();

      osparc.store.Store.getInstance().addGroup(nodesGroupService);

      this.fireDataEvent("finished");
    },

    __groupToWorkbenchData: function(nodesGroup) {
      let workbenchData = {};

      // serialize innerNodes
      const innerNodes = nodesGroup.getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        workbenchData[innerNode.getNodeId()] = innerNode.serialize();
      });

      // remove parent from first level
      const firstLevelNodes = nodesGroup.getInnerNodes(false);
      Object.values(firstLevelNodes).forEach(firstLevelNode => {
        workbenchData[firstLevelNode.getNodeId()]["parent"] = null;
      });

      // deep copy workbenchData
      workbenchData = osparc.utils.Utils.deepCloneObject(workbenchData);

      // removeOutReferences
      workbenchData = this.__removeOutReferences(workbenchData);

      // replace Uuids
      workbenchData = osparc.data.Converters.replaceUuids(workbenchData);

      return workbenchData;
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
