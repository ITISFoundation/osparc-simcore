/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.data.model.WorkbenchModel", {
  extend: qx.core.Object,

  construct: function(prjName, wbData) {
    this.base(arguments);

    this.__nodesTopLevel = {};

    this.setProjectName(prjName);
    this.createNodeModels(wbData);
    this.createLinks(wbData);
  },

  properties: {
    projectName: {
      check: "String",
      nullable: false
    }
  },

  events: {
    "WorkbenchModelChanged": "qx.event.type.Event",
    "ShowInLogger": "qx.event.type.Event"
  },

  members: {
    __nodesTopLevel: null,

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
      let nodes = Object.assign({}, this.__nodesTopLevel);
      if (recursive) {
        for (const nodeId in this.__nodesTopLevel) {
          let innerNodes = this.__nodesTopLevel[nodeId].getInnerNodes(true);
          nodes = Object.assign(nodes, innerNodes);
        }
      }
      return nodes;
    },

    getPath: function(nodeId) {
      let pathWithIds = this.getPathWithId(nodeId);
      let nodePath = [];
      for (let i=0; i<pathWithIds.length; i++) {
        nodePath.push(Object.values(pathWithIds[i])[0]);
      }
      return nodePath;
    },

    getPathWithId: function(nodeId) {
      let rootObj = {};
      rootObj["root"] = this.getProjectName();
      if (nodeId === "root" || nodeId === undefined) {
        return [rootObj];
      }

      const nodeModel = this.getNodeModel(nodeId);
      let nodePath = [];
      let obj = {};
      obj[nodeId] = nodeModel.getLabel();
      nodePath.unshift(obj);
      let parentNodeId = nodeModel.getParentNodeId();
      while (parentNodeId) {
        const checkThisNode = this.getNodeModel(parentNodeId);
        if (checkThisNode) {
          let thisObj = {};
          thisObj[parentNodeId] = checkThisNode.getLabel();
          nodePath.unshift(thisObj);
          parentNodeId = checkThisNode.getParentNodeId();
        }
      }
      nodePath.unshift(rootObj);
      return nodePath;
    },

    createNodeModel: function(key, version, uuid, nodeData) {
      let existingNodeModel = this.getNodeModel(uuid);
      if (existingNodeModel) {
        return existingNodeModel;
      }
      let nodeModel = new qxapp.data.model.NodeModel(key, version, uuid);
      nodeModel.populateNodeData(nodeData);
      nodeModel.addListener("ShowInLogger", e => {
        this.fireDataEvent("ShowInLogger", e.getData());
      }, this);
      return nodeModel;
    },

    createNodeModels: function(workbenchData) {
      let keys = Object.keys(workbenchData);
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        const nodeData = workbenchData[nodeId];
        if (Object.prototype.hasOwnProperty.call(nodeData, "parent") && nodeData["parent"] !== null) {
          let parentNode = this.getNodeModel(nodeData.parent);
          if (parentNode === null) {
            // If parent was not yet created, delay the creation of its' children
            keys.push(nodeId);
            // check if there is an inconsitency
            const nKeys = keys.length;
            if (nKeys > 1) {
              if (keys[nKeys-1] === keys[nKeys-2]) {
                console.log(nodeId, "will never be created, parent missing", nodeData.parent);
                return;
              }
            }
            continue;
          }
        }
        let nodeModel = null;
        if (Object.prototype.hasOwnProperty.call(nodeData, "key")) {
          // not container
          nodeModel = this.createNodeModel(nodeData.key, nodeData.version, nodeId, nodeData);
        } else {
          // container
          nodeModel = this.createNodeModel(null, null, nodeId, nodeData);
        }
        if (Object.prototype.hasOwnProperty.call(nodeData, "parent")) {
          let parentModel = this.getNodeModel(nodeData.parent);
          this.addNodeModel(nodeModel, parentModel);
        } else {
          this.addNodeModel(nodeModel);
        }
      }
    },

    addNodeModel: function(nodeModel, parentNodeModel) {
      const uuid = nodeModel.getNodeId();
      if (parentNodeModel) {
        parentNodeModel.addInnerNode(uuid, nodeModel);
        nodeModel.setParentNodeId(parentNodeModel.getNodeId());
      } else {
        this.__nodesTopLevel[uuid] = nodeModel;
      }
      this.fireEvent("WorkbenchModelChanged");
    },

    removeNode: function(nodeModel) {
      // TODO: only works with top level nodes
      const nodeId = nodeModel.getNodeId();
      const exists = Object.prototype.hasOwnProperty.call(this.__nodesTopLevel, nodeId);
      if (exists) {
        delete this.__nodesTopLevel[nodeModel.getNodeId()];
        this.fireEvent("WorkbenchModelChanged");
      }
      nodeModel.removeNode();
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
        return node.removeInputNode(outputNodeId);
      }
      return false;
    },

    serializeWorkbench: function(saveContainers = true, savePosition = true) {
      let workbench = {};
      const allModels = this.getNodeModels(true);
      for (const nodeId in allModels) {
        const nodeModel = allModels[nodeId];
        if (!saveContainers && nodeModel.isContainer()) {
          continue;
        }

        // node generic
        let node = workbench[nodeModel.getNodeId()] = {
          label: nodeModel.getLabel(),
          inputs: nodeModel.getInputValues(), // can a container have inputs?
          inputNodes: nodeModel.getInputNodes(),
          outputNode: nodeModel.getIsOutputNode(),
          outputs: nodeModel.getOutputValues(), // can a container have outputs?
          parent: nodeModel.getParentNodeId()
        };

        if (savePosition) {
          node.position = {
            x: nodeModel.getPosition().x,
            y: nodeModel.getPosition().y
          };
        }

        // node especific
        if (!nodeModel.isContainer()) {
          node.key = nodeModel.getMetaData().key;
          node.version = nodeModel.getMetaData().version;
        }
      }
      return workbench;
    }
  }
});
