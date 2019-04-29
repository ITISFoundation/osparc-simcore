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
 * It takes care of creating, storing and managing nodes and edges.
 *
 *                                    -> {EDGES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   study.setWorkbench(new qxapp.data.model.Workbench(study, study.workbench));
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
    this.__edges = {};

    this.setStudy(study);
    this.setStudyName(study.getName());

    this.__createNodes(wbData);
    this.__createEdges(wbData);
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
    __edges: null,

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
      const nodePath = [];
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

    getConnectedEdges: function(nodeId) {
      const connectedEdges = [];
      const edges = Object.values(this.__edges);
      for (const edge of edges) {
        if (edge.getInputNodeId() === nodeId) {
          connectedEdges.push(edge.getEdgeId());
        }
        if (edge.getOutputNodeId() === nodeId) {
          connectedEdges.push(edge.getEdgeId());
        }
      }
      return connectedEdges;
    },

    getEdge: function(edgeId, node1Id, node2Id) {
      const exists = Object.prototype.hasOwnProperty.call(this.__edges, edgeId);
      if (exists) {
        return this.__edges[edgeId];
      }
      const edges = Object.values(this.__edges);
      for (const edge of edges) {
        if (edge.getInputNodeId() === node1Id &&
          edge.getOutputNodeId() === node2Id) {
          return edge;
        }
      }
      return null;
    },

    createEdge: function(edgeId, node1Id, node2Id) {
      const existingEdge = this.getEdge(edgeId, node1Id, node2Id);
      if (existingEdge) {
        return existingEdge;
      }
      if (!qxapp.data.Permissions.getInstance().canDo("study.edge.create", true)) {
        return null;
      }
      const edge = new qxapp.data.model.Edge(edgeId, node1Id, node2Id);
      this.addEdge(edge);

      // post edge creation
      this.getNode(node2Id).edgeAdded(edge);

      return edge;
    },

    addEdge: function(edge) {
      const edgeId = edge.getEdgeId();
      const node1Id = edge.getInputNodeId();
      const node2Id = edge.getOutputNodeId();
      let exists = this.getEdge(edgeId, node1Id, node2Id);
      if (!exists) {
        this.__edges[edgeId] = edge;
      }
    },

    createNode: function(key, version, uuid, parent, populateNodeData) {
      const existingNode = this.getNode(uuid);
      if (existingNode) {
        return existingNode;
      }
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.create", true)) {
        return null;
      }
      const node = new qxapp.data.model.Node(this, key, version, uuid);
      const metaData = node.getMetaData();
      if (metaData && Object.prototype.hasOwnProperty.call(metaData, "innerNodes")) {
        const innerNodeMetaDatas = Object.values(metaData["innerNodes"]);
        for (const innerNodeMetaData of innerNodeMetaDatas) {
          this.createNode(innerNodeMetaData.key, innerNodeMetaData.version, null, node, true);
        }
      }
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
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.delete", true)) {
        return false;
      }

      // remove first the connected edges
      const connectedEdges = this.getConnectedEdges(nodeId);
      for (let i=0; i<connectedEdges.length; i++) {
        const edgeId = connectedEdges[i];
        this.removeEdge(edgeId);
      }

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

    __createEdge: function(outputNodeId, inputNodeId) {
      let node = this.getNode(inputNodeId);
      if (node) {
        node.addInputNode(outputNodeId);
      }
    },

    __createEdges: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        if (nodeData.inputNodes) {
          for (let i=0; i < nodeData.inputNodes.length; i++) {
            const outputNodeId = nodeData.inputNodes[i];
            this.__createEdge(outputNodeId, nodeId);
          }
        }
      }
    },

    removeEdge: function(edgeId) {
      const edge = this.getEdge(edgeId);
      if (edge) {
        const inputNodeId = edge.getInputNodeId();
        const outputNodeId = edge.getOutputNodeId();
        const node = this.getNode(outputNodeId);
        if (node) {
          node.removeInputNode(inputNodeId);
          delete this.__edges[edgeId];
          return true;
        }
      }
      return false;
    },

    clearProgressData: function() {
      const allNodes = this.getNodes(true);
      const nodes = Object.values(allNodes);
      for (const node of nodes) {
        if (!node.isDynamic()) {
          node.setProgress(0);
        }
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
