/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores Workbench data.
 *
 * It takes care of creating, storing and managing nodes and links.
 *
 *                                    -> {NODES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   study.setWorkbench(new qxapp.data.model.Workbench(study, prjData.workbench));
 * </pre>
 */

qx.Class.define("qxapp.data.model.Workbench", {
  extend: qx.core.Object,

  /**
    * @param study {qxapp.data.model.Study} Study owning the Workbench
    * @param wbData {qx.core.Object} Object containing the workbench raw data
    */
  construct: function(study, wbData) {
    this.base(arguments);

    this.__nodesTopLevel = {};
    this.__links = {};

    this.setStudy(study);
    this.setStudyName(study.getName());

    this.__createNodes(wbData);
    this.__createLinks(wbData);
  },

  properties: {
    study: {
      check: "qxapp.data.model.Study",
      nullable: false
    },

    studyName: {
      check: "String",
      nullable: false
    }
  },

  events: {
    "workbenchChanged": "qx.event.type.Event",
    "updatePipeline": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data"
  },

  members: {
    __nodesTopLevel: null,
    __links: null,

    isContainer: function() {
      return false;
    },

    getNode: function(nodeId) {
      const allNodes = this.getNodes(true);
      const exists = Object.prototype.hasOwnProperty.call(allNodes, nodeId);
      if (exists) {
        return allNodes[nodeId];
      }
      return null;
    },

    getNodes: function(recursive = false) {
      let nodes = Object.assign({}, this.__nodesTopLevel);
      if (recursive) {
        let topLevelNodes = Object.values(this.__nodesTopLevel);
        for (const topLevelNode of topLevelNodes) {
          let innerNodes = topLevelNode.getInnerNodes(true);
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
      const node = this.getNode(nodeId);
      let parentNodeId = node.getParentNodeId();
      while (parentNodeId) {
        const checkThisNode = this.getNode(parentNodeId);
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
      const links = Object.values(this.__links);
      for (const link of links) {
        if (link.getInputNodeId() === nodeId) {
          connectedLinks.push(link.getLinkId());
        }
        if (link.getOutputNodeId() === nodeId) {
          connectedLinks.push(link.getLinkId());
        }
      }
      return connectedLinks;
    },

    getLink: function(linkId, node1Id, node2Id) {
      const exists = Object.prototype.hasOwnProperty.call(this.__links, linkId);
      if (exists) {
        return this.__links[linkId];
      }
      const links = Object.values(this.__links);
      for (const link of links) {
        if (link.getInputNodeId() === node1Id &&
          link.getOutputNodeId() === node2Id) {
          return link;
        }
      }
      return null;
    },

    createLink: function(linkId, node1Id, node2Id) {
      let existingLink = this.getLink(linkId, node1Id, node2Id);
      if (existingLink) {
        return existingLink;
      }
      let link = new qxapp.data.model.Link(linkId, node1Id, node2Id);
      this.addLink(link);

      // post link creation
      this.getNode(node2Id).linkAdded(link);

      return link;
    },

    addLink: function(link) {
      const linkId = link.getLinkId();
      const node1Id = link.getInputNodeId();
      const node2Id = link.getOutputNodeId();
      let exists = this.getLink(linkId, node1Id, node2Id);
      if (!exists) {
        this.__links[linkId] = link;
      }
    },

    createNode: function(key, version, uuid, parent, populateNodeData) {
      let existingNode = this.getNode(uuid);
      if (existingNode) {
        return existingNode;
      }
      let node = new qxapp.data.model.Node(this, key, version, uuid);
      node.addListener("showInLogger", e => {
        this.fireDataEvent("showInLogger", e.getData());
      }, this);
      node.addListener("updatePipeline", e => {
        this.fireDataEvent("updatePipeline", e.getData());
      }, this);
      if (populateNodeData) {
        node.populateNodeData();
        node.giveUniqueName();
      }
      this.addNode(node, parent);

      return node;
    },

    cloneNode: function(nodeToClone) {
      const key = nodeToClone.getKey();
      const version = nodeToClone.getVersion();
      const parentNode = this.getNode(nodeToClone.getParentNodeId());
      let node = this.createNode(key, version, null, parentNode, true);
      const nodeData = nodeToClone.serialize();
      node.setInputData(nodeData);
      node.setOutputData(nodeData);
      node.setInputNodes(nodeData);
      node.setIsOutputNode(nodeToClone.getIsOutputNode());
      return node;
    },

    __createNodes: function(workbenchData) {
      let keys = Object.keys(workbenchData);
      // Create first all the nodes
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        const nodeData = workbenchData[nodeId];
        if (nodeData.parent && nodeData.parent !== null) {
          let parentNode = this.getNode(nodeData.parent);
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
        let parentNode = null;
        if (nodeData.parent) {
          parentNode = this.getNode(nodeData.parent);
        }
        if (nodeData.key) {
          // not container
          this.createNode(nodeData.key, nodeData.version, nodeId, parentNode, false);
        } else {
          // container
          this.createNode(null, null, nodeId, parentNode, false);
        }
      }

      // Then populate them (this will avoid issues of connecting nodes that might not be created yet)
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        const nodeData = workbenchData[nodeId];
        this.getNode(nodeId).populateNodeData(nodeData);
      }
      for (let i=0; i<keys.length; i++) {
        const nodeId = keys[i];
        this.getNode(nodeId).giveUniqueName();
      }
    },

    addNode: function(node, parentNode) {
      const uuid = node.getNodeId();
      if (parentNode) {
        parentNode.addInnerNode(uuid, node);
      } else {
        this.__nodesTopLevel[uuid] = node;
      }
      this.fireEvent("workbenchChanged");
    },

    removeNode: function(nodeId) {
      let node = this.getNode(nodeId);
      if (node) {
        node.removeNode();
        const isTopLevel = Object.prototype.hasOwnProperty.call(this.__nodesTopLevel, nodeId);
        if (isTopLevel) {
          delete this.__nodesTopLevel[nodeId];
        }
        this.fireEvent("workbenchChanged");
        return true;
      }
      return false;
    },

    __createLink: function(outputNodeId, inputNodeId) {
      let node = this.getNode(inputNodeId);
      if (node) {
        node.addInputNode(outputNodeId);
      }
    },

    __createLinks: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        if (nodeData.inputNodes) {
          for (let i=0; i < nodeData.inputNodes.length; i++) {
            const outputNodeId = nodeData.inputNodes[i];
            this.__createLink(outputNodeId, nodeId);
          }
        }
      }
    },

    removeLink: function(linkId) {
      let link = this.getLink(linkId);
      if (link) {
        const inputNodeId = link.getInputNodeId();
        const outputNodeId = link.getOutputNodeId();
        let node = this.getNode(outputNodeId);
        if (node) {
          node.removeInputNode(inputNodeId);
          delete this.__links[linkId];
          return true;
        }
      }
      return false;
    },

    clearProgressData: function() {
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        node.setProgress(0);
      }
    },

    serializeWorkbench: function(saveContainers = true, savePosition = true) {
      let workbench = {};
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        const data = node.serialize(saveContainers, savePosition);
        if (data) {
          workbench[node.getNodeId()] = data;
        }
      }
      return workbench;
    }
  }
});
