qx.Class.define("qxapp.data.model.WorkbenchModel", {
  extend: qx.core.Object,

  construct: function(wbData) {
    this.base(arguments);

    this.__nodes = {};
    this.createNodes(wbData);

    this.__links = {};
    this.createLinks(wbData);
  },

  events: {
    "WorkbenchModelChanged": "qx.event.type.Event"
  },

  members: {
    __nodes: null,
    __links: null,

    getNode: function(nodeId) {
      return this.__nodes[nodeId];
    },

    getNodes: function() {
      return this.__nodes;
    },

    createNode: function(nodeData, uuid) {
      let existingNodeModel = this.getNode(uuid);
      if (existingNodeModel) {
        return existingNodeModel;
      }
      const nodeImageId = nodeData.key + "-" + nodeData.version;
      let nodeModel = new qxapp.data.model.NodeModel(nodeImageId, uuid);
      nodeModel.populateNodeData(nodeData);
      uuid = nodeModel.getNodeId();
      this.__nodes[uuid] = nodeModel;
      this.fireEvent("WorkbenchModelChanged");
      return nodeModel;
    },

    createNodes: function(workbenchData) {
      for (const key of Object.keys(workbenchData)) {
        const nodeData = workbenchData[key];
        this.createNode(nodeData, key);
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

    getLinks: function() {
      return this.__links;
    },

    createLinks: function(workbenchData) {
      for (const key of Object.keys(workbenchData)) {
        const nodeData = workbenchData[key];
        if (nodeData.inputs) {
          for (const inputPortId in nodeData.inputs) {
            let link = nodeData.inputs[inputPortId];
            if (typeof link == "object" && link.nodeUuid) {
              const linkObj = {
                output: {
                  nodeUuid: link.nodeUuid,
                  output: link.output
                },
                input: {
                  nodeUuid: key,
                  input: inputPortId
                }
              };
              const linkId = qxapp.utils.Utils.uuidv4();
              this.__links[linkId] = linkObj;
              this.fireEvent("WorkbenchModelChanged");
            }
          }
        }
      }
    },

    removeLink: function(link) {
      const linkId = link.getLinkId();
      const exists = Object.prototype.hasOwnProperty.call(this.__links, linkId);
      if (exists) {
        let node2 = this.getNode(link.getOutputNodeId());
        if (node2) {
          node2.removeLink(link);
        }
      }
      this.fireEvent("WorkbenchModelChanged");
      return exists;
    },

    serializeWorkbench: function(savePosition = false) {
      let workbench = {};
      for (const nodeId of Object.keys(this.getNodes())) {
        const nodeModel = this.getNode(nodeId);
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
        for (let key in nodeModel.getInputPorts()) {
          const linkPort = this.__getInputPortLinked(nodeModel.getNodeId(), key);
          if (linkPort) {
            cNode.inputs[key] = linkPort;
          }
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
