/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.data.model.WorkbenchModel", {
  extend: qx.core.Object,

  construct: function(wbData) {
    this.base(arguments);

    this.__nodes = {};
    this.createNodeModels(wbData);
    this.createLinks(wbData);
  },

  events: {
    "WorkbenchModelChanged": "qx.event.type.Event"
  },

  members: {
    __nodes: null,

    isContainer: function() {
      return false;
    },

    getNodeModel: function(nodeId) {
      const allNodes = this.getNodeModels(true);
      const exists = Object.prototype.hasOwnProperty.call(allNodes, nodeId);
      if (exists) {
        return allNodes[nodeId];
      }
      return null;
    },

    getNodeModels: function(recursive = false) {
      let nodes = Object.assign({}, this.__nodes);
      if (recursive) {
        for (const nodeId in this.__nodes) {
          let innerNodes = this.__nodes[nodeId].getInnerNodes(true);
          nodes = Object.assign(nodes, innerNodes);
        }
      }
      return nodes;
    },

    createNodeModel: function(metaData, uuid, nodeData) {
      let existingNodeModel = this.getNodeModel(uuid);
      if (existingNodeModel) {
        return existingNodeModel;
      }
      let nodeModel = new qxapp.data.model.NodeModel(metaData, uuid);
      nodeModel.populateNodeData(nodeData);
      uuid = nodeModel.getNodeId();
      this.__nodes[uuid] = nodeModel;
      this.fireEvent("WorkbenchModelChanged");
      return nodeModel;
    },

    createNodeModels: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        let store = qxapp.data.Store.getInstance();
        let metaData = store.getNodeMetaData(nodeData);
        this.createNodeModel(metaData, nodeId, nodeData);
      }
    },

    removeNode: function(nodeModel) {
      const nodeId = nodeModel.getNodeId();
      const exists = Object.prototype.hasOwnProperty.call(this.__nodes, nodeId);
      if (exists) {
        if (nodeModel.getMetaData().type == "dynamic") {
          const slotName = "stopDynamic";
          let socket = qxapp.wrappers.WebSocket.getInstance();
          let data = {
            nodeId: nodeModel.getNodeId()
          };
          socket.emit(slotName, data);
        }
        delete this.__nodes[nodeModel.getNodeId()];
        this.fireEvent("WorkbenchModelChanged");
      }
      return exists;
    },

    createLink: function(outputNodeId, inputNodeId) {
      let node = this.getNodeModel(inputNodeId);
      if (node) {
        node.addInputNode(outputNodeId);
      }
    },

    createLinks: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        if (nodeData.inputNodes) {
          for (let i=0; i < nodeData.inputNodes.length; i++) {
            const outputNodeId = nodeData.inputNodes[i];
            this.createLink(outputNodeId, nodeId);
          }
        }
      }
    },

    removeLink: function(outputNodeId, inputNodeId) {
      let node = this.getNodeModel(inputNodeId);
      if (node) {
        return node.removeLink(outputNodeId);
      }
      return false;
    },

    serializeWorkbench: function(savePosition = false) {
      let workbench = {};
      for (const nodeId in this.getNodeModels()) {
        const nodeModel = this.getNodeModel(nodeId);
        const nodeData = nodeModel.getMetaData();
        // let cNode = workbench[nodeModel.getNodeId()] = {
        workbench[nodeModel.getNodeId()] = {
          key: nodeData.key,
          version: nodeData.version,
          inputs: nodeModel.getInputValues(),
          outputs: {}
        };
        /*
        if (savePosition && this.__desktop.indexOf(nodeModel)>-1) {
          cNode.position = {
            x: nodeModel.getPosition().x,
            y: nodeModel.getPosition().y
          };
        }
        for (let key in nodeData.outputs) {
          const outputPort = nodeData.outputs[key];
          if ("value" in outputPort) {
            cNode.outputs[key] = outputPort.value;
          }
        }
        */
      }
      return workbench;
    }
  }
});
