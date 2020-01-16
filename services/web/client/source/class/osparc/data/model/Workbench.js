/* ************************************************************************

   osparc - the simcore frontend

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
 *   const workbench = new osparc.data.model.Workbench(study.workbench)
 *   study.setWorkbench(workbench);
 *   workbench.initWorkbench();
 * </pre>
 */

qx.Class.define("osparc.data.model.Workbench", {
  extend: qx.core.Object,

  /**
    * @param workbenchData {Object} Object containing the workbench raw data
    */
  construct: function(workbenchData) {
    this.base(arguments);

    this.__workbenchInitData = workbenchData;
  },

  events: {
    "workbenchChanged": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data"
  },

  members: {
    __workbenchInitData: null,
    __rootNodes: null,
    __edges: null,

    buildWorkbench: function() {
      this.__rootNodes = {};
      this.__edges = {};
      this.__deserializeWorkbench(this.__workbenchInitData);
      this.__workbenchInitData = null;
    },

    initWorkbench: function() {
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        node.addDynamicButtons();
        node.startDynamicService();
      }
    },

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
      let nodes = Object.assign({}, this.__rootNodes);
      if (recursive) {
        let topLevelNodes = Object.values(this.__rootNodes);
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
      if (!osparc.data.Permissions.getInstance().canDo("study.edge.create", true)) {
        return null;
      }
      const edge = new osparc.data.model.Edge(edgeId, node1Id, node2Id);
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

    createNode: function(key, version, uuid, parent) {
      const existingNode = this.getNode(uuid);
      if (existingNode) {
        return existingNode;
      }
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        return null;
      }
      const node = new osparc.data.model.Node(key, version, uuid);
      const metaData = node.getMetaData();
      if (metaData && Object.prototype.hasOwnProperty.call(metaData, "innerNodes")) {
        const innerNodeMetaDatas = Object.values(metaData["innerNodes"]);
        for (const innerNodeMetaData of innerNodeMetaDatas) {
          this.createNode(innerNodeMetaData.key, innerNodeMetaData.version, null, node);
        }
      }
      this.__initNodeSignals(node);

      node.populateNodeData();
      node.giveUniqueName();

      // create the node in the backend here
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const params = {
        url: {
          projectId: study.getUuid()
        },
        data: {
          "service_id": node.getNodeId(),
          "service_key": key,
          "service_version": version
        }
      };
      this.addNode(node, parent);
      node.addDynamicButtons();

      osparc.data.Resources.fetch("studies", "addNode", params)
        .then(data => {
          node.startDynamicService();
        })
        .catch(err => {
          const errorMsg = "Error when starting " + metaData.key + ":" + metaData.version + ": " + err.getTarget().getResponse()["error"];
          const errorMsgData = {
            nodeId: node.getNodeId(),
            msg: errorMsg
          };
          node.fireDataEvent("showInLogger", errorMsgData);
          node.setInteractiveStatus("failed");
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while starting the node."), "ERROR");
        });

      return node;
    },

    __initNodeSignals: function(node) {
      if (node) {
        node.addListener("showInLogger", e => {
          this.fireDataEvent("showInLogger", e.getData());
        }, this);
        node.addListener("retrieveInputs", e => {
          this.fireDataEvent("retrieveInputs", e.getData());
        }, this);
      }
    },

    cloneNode: function(nodeToClone) {
      const key = nodeToClone.getKey();
      const version = nodeToClone.getVersion();
      const parentNode = this.getNode(nodeToClone.getParentNodeId());
      let node = this.createNode(key, version, null, parentNode);
      const nodeData = nodeToClone.serialize();
      node.setInputData(nodeData);
      node.setOutputData(nodeData);
      node.setInputNodes(nodeData);
      node.setIsOutputNode(nodeToClone.getIsOutputNode());
      return node;
    },

    addNode: function(node, parentNode) {
      const nodeId = node.getNodeId();
      if (parentNode) {
        parentNode.addInnerNode(nodeId, node);
      } else {
        this.__rootNodes[nodeId] = node;
        node.setParentNodeId(null);
      }
      this.fireEvent("workbenchChanged");
    },

    moveNode: function(node, newParent, oldParent) {
      const nodeId = node.getNodeId();
      if (oldParent === null) {
        delete this.__rootNodes[nodeId];
      } else {
        oldParent.removeInnerNode(nodeId);
      }
      if (newParent === null) {
        this.__rootNodes[nodeId] = node;
        node.setParentNodeId(null);
      } else {
        newParent.addInnerNode(nodeId, node);
      }
    },

    removeNode: function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.delete", true)) {
        return false;
      }
      // remove node in the backend
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const params = {
        url: {
          projectId: study.getUuid(),
          nodeId: nodeId
        }
      };
      osparc.data.Resources.fetch("studies", "deleteNode", params)
        .catch(err => console.error(err));

      // remove first the connected edges
      const connectedEdges = this.getConnectedEdges(nodeId);
      for (let i=0; i<connectedEdges.length; i++) {
        const edgeId = connectedEdges[i];
        this.removeEdge(edgeId);
      }

      let node = this.getNode(nodeId);
      if (node) {
        node.removeNode();
        const isTopLevel = Object.prototype.hasOwnProperty.call(this.__rootNodes, nodeId);
        if (isTopLevel) {
          delete this.__rootNodes[nodeId];
        }
        this.fireEvent("workbenchChanged");
        return true;
      }
      return false;
    },

    removeEdge: function(edgeId, currentNodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.edge.delete", true)) {
        return false;
      }

      const edge = this.getEdge(edgeId);
      if (currentNodeId !== undefined) {
        const currentNode = this.getNode(currentNodeId);
        if (currentNode && currentNode.isContainer() && edge.getOutputNodeId() === currentNode.getNodeId()) {
          const inputNode = this.getNode(edge.getInputNodeId());
          inputNode.setIsOutputNode(false);

          // Remove also dependencies from outter nodes
          const cNodeId = inputNode.getNodeId();
          const allNodes = this.getNodes(true);
          for (const nodeId in allNodes) {
            const node = allNodes[nodeId];
            if (node.isInputNode(cNodeId) && !currentNode.isInnerNode(node.getNodeId())) {
              this.removeEdge(edgeId);
            }
          }
        }
      }

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
        if (node.isComputational() && !node.isInKey("file-picker")) {
          node.setProgress(0);
        }
      }
    },

    __deserializeWorkbench: function(workbenchData) {
      this.__deserializeNodes(workbenchData);
      this.__deserializeEdges(workbenchData);
    },

    __deserializeNodes: function(workbenchData) {
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
        const node = new osparc.data.model.Node(nodeData.key, nodeData.version, nodeId);
        this.__initNodeSignals(node);
        let parentNode = null;
        if (nodeData.parent) {
          parentNode = this.getNode(nodeData.parent);
        }
        this.addNode(node, parentNode);
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

    __deserializeEdges: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        const node = this.getNode(nodeId);
        if (node === null) {
          continue;
        }
        if (nodeData.inputNodes) {
          for (let i=0; i < nodeData.inputNodes.length; i++) {
            const outputNodeId = nodeData.inputNodes[i];
            const edge = new osparc.data.model.Edge(null, outputNodeId, nodeId);
            this.addEdge(edge);
            node.addInputNode(outputNodeId);
          }
        }
        if (nodeData.outputNode) {
          const edge = new osparc.data.model.Edge(null, nodeId, nodeData.parent);
          this.addEdge(edge);
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
