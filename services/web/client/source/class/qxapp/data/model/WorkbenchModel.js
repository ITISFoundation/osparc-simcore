/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.data.model.WorkbenchModel", {
  extend: qx.core.Object,

  construct: function(prjName, wbData) {
    this.base(arguments);

    this.__nodesTopLevel = {};
    this.__links = {};

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
    "NodeAdded": "qx.event.type.Data",
    "UpdatePipeline": "qx.event.type.Data",
    "ShowInLogger": "qx.event.type.Data"
  },

  members: {
    __nodesTopLevel: null,
    __links: null,

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

    getPathIds: function(nodeId) {
      if (nodeId === "root" || nodeId === undefined) {
        return ["root"];
      }
      let nodePath = [];
      nodePath.unshift(nodeId);
      const nodeModel = this.getNodeModel(nodeId);
      let parentNodeId = nodeModel.getParentNodeId();
      while (parentNodeId) {
        const checkThisNode = this.getNodeModel(parentNodeId);
        if (checkThisNode) {
          nodePath.unshift(parentNodeId);
          parentNodeId = checkThisNode.getParentNodeId();
        }
      }
      nodePath.unshift("root");
      return nodePath;
    },

    getConnectedLinks: function(nodeId) {
      let connectedLinks = [];
      for (const linkId in this.__links) {
        const link = this.__links[linkId];
        if (link.getInputNodeId() === nodeId) {
          connectedLinks.push(link.getLinkId());
        }
        if (link.getOutputNodeId() === nodeId) {
          connectedLinks.push(link.getLinkId());
        }
      }
      return connectedLinks;
    },

    getLinkModel: function(linkId, node1Id, node2Id) {
      const exists = Object.prototype.hasOwnProperty.call(this.__links, linkId);
      if (exists) {
        return this.__links[linkId];
      }
      for (const id in this.__links) {
        const link = this.__links[id];
        if (link.getInputNodeId() === node1Id &&
          link.getOutputNodeId() === node2Id) {
          return this.__links[id];
        }
      }
      return null;
    },

    createLinkModel: function(linkId, node1Id, node2Id) {
      let existingLinkModel = this.getLinkModel(linkId, node1Id, node2Id);
      if (existingLinkModel) {
        return existingLinkModel;
      }
      let linkModel = new qxapp.data.model.LinkModel(linkId, node1Id, node2Id);
      return linkModel;
    },

    addLinkModel: function(linkModel) {
      const linkId = linkModel.getLinkId();
      const node1Id = linkModel.getInputNodeId();
      const node2Id = linkModel.getOutputNodeId();
      let exists = this.getLinkModel(linkId, node1Id, node2Id);
      if (!exists) {
        this.__links[linkId] = linkModel;
        // this.fireEvent("WorkbenchModelChanged");
      }
    },

    createNodeModel: function(key, version, uuid, nodeData) {
      let existingNodeModel = this.getNodeModel(uuid);
      if (existingNodeModel) {
        return existingNodeModel;
      }
      let nodeModel = new qxapp.data.model.NodeModel(this, key, version, uuid);
      nodeModel.addListener("ShowInLogger", e => {
        this.fireDataEvent("ShowInLogger", e.getData());
      }, this);
      nodeModel.addListener("UpdatePipeline", e => {
        this.fireDataEvent("UpdatePipeline", e.getData());
      }, this);
      this.fireDataEvent("NodeAdded", nodeModel);
      if (nodeData) {
        nodeModel.populateNodeData(nodeData);
      }
      return nodeModel;
    },

    createNodeModels: function(workbenchData) {
      let keys = Object.keys(workbenchData);
      // Create first all the nodes
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        const nodeData = workbenchData[nodeId];
        if (nodeData.parent && nodeData.parent !== null) {
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
        if (nodeData.key) {
          // not container
          nodeModel = this.createNodeModel(nodeData.key, nodeData.version, nodeId);
        } else {
          // container
          nodeModel = this.createNodeModel(null, null, nodeId, nodeData);
        }
        if (nodeData.parent) {
          let parentModel = this.getNodeModel(nodeData.parent);
          this.addNodeModel(nodeModel, parentModel);
        } else {
          this.addNodeModel(nodeModel);
        }
      }

      // Then populate them (this will avoid issues of connecting nodes that might not be created yet)
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        const nodeData = workbenchData[nodeId];
        this.getNodeModel(nodeId).populateNodeData(nodeData);
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

    removeNode: function(nodeId) {
      let nodeModel = this.getNodeModel(nodeId);
      if (nodeModel) {
        const isTopLevel = Object.prototype.hasOwnProperty.call(this.__nodesTopLevel, nodeId);
        if (isTopLevel) {
          delete this.__nodesTopLevel[nodeId];
        }
        const parentNodeId = nodeModel.getParentNodeId();
        if (parentNodeId) {
          let parentNodeModel = this.getNodeModel(parentNodeId);
          parentNodeModel.removeInnerNode(nodeId);
        }
        nodeModel.removeNode();
        this.fireEvent("WorkbenchModelChanged");
        return true;
      }
      return false;
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

    removeLink: function(linkId) {
      let linkModel = this.getLinkModel(linkId);
      if (linkModel) {
        const inputNodeId = linkModel.getInputNodeId();
        const outputNodeId = linkModel.getOutputNodeId();
        let node = this.getNodeModel(outputNodeId);
        if (node) {
          node.removeInputNode(inputNodeId);
          delete this.__links[linkId];
          return true;
        }
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
          node.key = nodeModel.getKey();
          node.version = nodeModel.getVersion();
        }
      }
      return workbench;
    }
  }
});
