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
  construct: function(workbenchData, workbenchUIData) {
    this.base(arguments);

    this.__workbenchInitData = workbenchData;
    this.__workbenchUIInitData = workbenchUIData;
  },

  events: {
    "nNodesChanged": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Data",
    "openNode": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data"
  },

  members: {
    __workbenchInitData: null,
    __workbenchUIInitData: null,
    __rootNodes: null,
    __edges: null,

    buildWorkbench: function() {
      this.__rootNodes = {};
      this.__edges = {};
      this.__deserialize(this.__workbenchInitData, this.__workbenchUIInitData);
      this.__workbenchInitData = null;
      this.__workbenchUIInitData = null;
    },

    initWorkbench: function() {
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
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
      if (recursive && this.__rootNodes) {
        let topLevelNodes = Object.values(this.__rootNodes);
        for (const topLevelNode of topLevelNodes) {
          let innerNodes = topLevelNode.getInnerNodes(true);
          nodes = Object.assign(nodes, innerNodes);
        }
      }
      return nodes;
    },

    getPathIds: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const studyId = study.getUuid();
      if (nodeId === studyId || nodeId === undefined) {
        return [studyId];
      }
      const nodePath = [];
      nodePath.unshift(nodeId);
      const node = this.getNode(nodeId);
      if (node) {
        let parentNodeId = node.getParentNodeId();
        while (parentNodeId) {
          const checkThisNode = this.getNode(parentNodeId);
          if (checkThisNode) {
            nodePath.unshift(parentNodeId);
            parentNodeId = checkThisNode.getParentNodeId();
          }
        }
      }
      nodePath.unshift(studyId);
      return nodePath;
    },

    getConnectedEdges: function(nodeId) {
      const connectedEdges = [];
      const edges = Object.values(this.__edges);
      for (const edge of edges) {
        const inputNodeId = edge.getInputNodeId();
        const outputNodeId = edge.getOutputNodeId();
        if ([inputNodeId, outputNodeId].includes(nodeId)) {
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
      const node1 = this.getNode(node1Id);
      const node2 = this.getNode(node2Id);
      if (node1 && node2) {
        const edge = new osparc.data.model.Edge(edgeId, node1, node2);
        this.addEdge(edge);

        // post edge creation
        this.getNode(node2Id).edgeAdded(edge);

        return edge;
      }
      return null;
    },

    addEdge: function(edge) {
      const edgeId = edge.getEdgeId();
      const node1Id = edge.getInputNodeId();
      const node2Id = edge.getOutputNodeId();
      const exists = this.getEdge(edgeId, node1Id, node2Id);
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
      this.addNode(node, parent);

      this.__initNodeSignals(node);

      node.populateNodeData();
      node.giveUniqueName();
      node.startInBackend();

      const metaData = node.getMetaData();
      if (metaData && Object.prototype.hasOwnProperty.call(metaData, "workbench")) {
        this.__createInnerWorkbench(node, metaData);
      }

      return node;
    },

    __createInnerWorkbench: function(parentNode, metaData) {
      // this is must be a nodes group
      const workbench = osparc.data.Converters.replaceUuids(metaData["workbench"]);
      for (let innerNodeId in workbench) {
        workbench[innerNodeId]["parent"] = workbench[innerNodeId]["parent"] || parentNode.getNodeId();
      }

      this.__deserialize(workbench);

      for (let innerNodeId in workbench) {
        this.getNode(innerNodeId).startInBackend();
      }
    },

    __initNodeSignals: function(node) {
      if (node) {
        node.addListener("showInLogger", e => {
          this.fireDataEvent("showInLogger", e.getData());
        }, this);
        node.addListener("retrieveInputs", e => {
          this.fireDataEvent("retrieveInputs", e.getData());
        }, this);
        node.addListener("filePickerRequested", e => {
          const {
            portId,
            nodeId
          } = e.getData();
          this.__filePickerRequested(nodeId, portId);
        }, this);
      }
    },

    __filePickerRequested: function(nodeId, portId) {
      // Create/Reuse File Picker. Reuse it if a File Picker is already
      // connecteted and it is not used anywhere else
      const requesterNode = this.getNode(nodeId);
      const link = requesterNode.getPropsForm().getLink(portId);
      let isUsed = false;
      if (link) {
        const connectedFPID = link["nodeUuid"];
        // check if it's used by another port
        const links1 = requesterNode.getPropsForm().getLinks();
        const matches = links1.filter(link1 => link1["nodeUuid"] === connectedFPID);
        isUsed = matches.length > 1;

        // check if it's used by other nodes
        const allNodes = this.getNodes(true);
        const nodeIds = Object.keys(allNodes);
        for (let i=0; i<nodeIds.length && !isUsed; i++) {
          const nodeId2 = nodeIds[i];
          if (nodeId === nodeId2) {
            continue;
          }
          const node = allNodes[nodeId2];
          const links2 = node.getPropsForm() ? node.getPropsForm().getLinks() : [];
          isUsed = links2.some(link2 => link2["nodeUuid"] === connectedFPID);
        }
      }

      if (link === null || isUsed) {
        // do not overlap the new FP with other nodes
        const pos = requesterNode.getPosition();
        const nodeWidth = osparc.component.workbench.NodeUI.NODE_WIDTH;
        const nodeHeight = osparc.component.workbench.NodeUI.NODE_HEIGHT;
        const xPos = Math.max(0, pos.x-nodeWidth-30);
        let posY = pos.y;
        const allNodes = this.getNodes();
        const avoidY = [];
        for (const nId in allNodes) {
          const node = allNodes[nId];
          if (node.getPosition().x >= xPos-nodeWidth && node.getPosition().x <= (xPos+nodeWidth)) {
            avoidY.push(node.getPosition().y);
          }
        }
        avoidY.sort((a, b) => a - b); // For ascending sort
        avoidY.forEach(y => {
          if (posY >= y-nodeHeight && posY <= (y+nodeHeight)) {
            posY = y+nodeHeight+20;
          }
        });

        // create a new FP
        const fpMD = osparc.utils.Services.getFilePicker();
        const parentNodeId = requesterNode.getParentNodeId();
        const parent = parentNodeId ? this.getNode(parentNodeId) : null;
        const fp = this.createNode(fpMD["key"], fpMD["version"], null, parent);
        fp.setPosition({
          x: xPos,
          y: posY
        });

        // remove old connection if any
        if (link !== null) {
          requesterNode.getPropsForm().removeLink(portId);
        }

        // create connection
        const fpId = fp.getNodeId();
        requesterNode.addInputNode(fpId);
        requesterNode.addPortLink(portId, fpId, "outFile")
          .then(success => {
            if (success) {
              this.fireDataEvent("openNode", fpId);
            } else {
              this.removeNode(fpId);
              const msg = qx.locale.Manager.tr("File couldn't be assigned");
              osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
            }
          });
      } else {
        const connectedFPID = link["nodeUuid"];
        this.fireDataEvent("openNode", connectedFPID);
      }
    },

    addNode: function(node, parentNode) {
      const nodeId = node.getNodeId();
      if (parentNode) {
        parentNode.addInnerNode(nodeId, node);
      } else {
        this.__rootNodes[nodeId] = node;
      }
      node.setParentNodeId(parentNode ? parentNode.getNodeId() : null);
      this.fireEvent("nNodesChanged");
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
      } else {
        newParent.addInnerNode(nodeId, node);
      }
      node.setParentNodeId(newParent ? newParent.getNodeId() : null);
    },

    removeNode: function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.delete", true)) {
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
        const isTopLevel = Object.prototype.hasOwnProperty.call(this.__rootNodes, nodeId);
        if (isTopLevel) {
          delete this.__rootNodes[nodeId];
        }
        this.fireEvent("nNodesChanged");
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
          currentNode.removeOutputNode(inputNode.getNodeId());

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
          node.removeNodePortConnections(inputNodeId);
          delete this.__edges[edgeId];
          return true;
        }
      }
      return false;
    },

    __deserialize: function(workbenchData, workbenchUIData) {
      this.__deserializeNodes(workbenchData, workbenchUIData);
      this.__deserializeEdges(workbenchData);
    },

    __deserializeNodes: function(workbenchData, workbenchUIData = {}) {
      const nodeIds = Object.keys(workbenchData);
      // Create first all the nodes
      for (let i=0; i<nodeIds.length; i++) {
        const nodeId = nodeIds[i];
        const nodeData = workbenchData[nodeId];
        if (nodeData.parent && nodeData.parent !== null) {
          let parentNode = this.getNode(nodeData.parent);
          if (parentNode === null) {
            // If parent was not yet created, delay the creation of its' children
            nodeIds.push(nodeId);
            // check if there is an inconsitency
            const nKeys = nodeIds.length;
            if (nKeys > 1) {
              if (nodeIds[nKeys-1] === nodeIds[nKeys-2]) {
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
      this.__populateNodesData(workbenchData, workbenchUIData);

      nodeIds.forEach(nodeId => {
        this.getNode(nodeId).giveUniqueName();
      });
    },

    __populateNodesData: function(workbenchData, workbenchUIData) {
      Object.entries(workbenchData).forEach(([nodeId, nodeData]) => {
        this.getNode(nodeId).populateNodeData(nodeData);
        if ("position" in nodeData) {
          this.getNode(nodeId).populateNodeUIData(nodeData);
        }
        if (workbenchUIData && "workbench" in workbenchUIData && nodeId in workbenchUIData.workbench) {
          this.getNode(nodeId).populateNodeUIData(workbenchUIData.workbench[nodeId]);
        }
      });
    },

    __deserializeEdges: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        const node = this.getNode(nodeId);
        if (node === null) {
          continue;
        }
        this.__addInputOutputNodesAndEdges(node, nodeData.inputNodes, true);
        this.__addInputOutputNodesAndEdges(node, nodeData.outputNodes, false);
      }
    },

    __addInputOutputNodesAndEdges: function(node, inputOutputNodeIds, isInput) {
      if (inputOutputNodeIds) {
        inputOutputNodeIds.forEach(inputOutputNodeId => {
          const node1 = this.getNode(inputOutputNodeId);
          if (node1 === null) {
            return;
          }
          const edge = new osparc.data.model.Edge(null, node1, node);
          this.addEdge(edge);
          if (isInput) {
            node.addInputNode(inputOutputNodeId);
          } else {
            node.addOutputNode(inputOutputNodeId);
          }
        });
      }
    },

    __getBrotherNodes: function(currentModel, excludeNodeIds) {
      let brotherNodesObj = {};
      if (currentModel.getNodeId) {
        brotherNodesObj = currentModel.getInnerNodes(false);
      } else {
        brotherNodesObj = this.getNodes(false);
      }

      const brotherNodes = [];
      for (const brotherNodeId in brotherNodesObj) {
        const index = excludeNodeIds.indexOf(brotherNodeId);
        if (index === -1) {
          const brotherNode = this.getNode(brotherNodeId);
          brotherNodes.push(brotherNode);
        }
      }
      return brotherNodes;
    },

    __getAveragePosition: function(nodes) {
      let avgX = 0;
      let avgY = 0;
      nodes.forEach(node => {
        avgX += node.getPosition().x;
        avgY += node.getPosition().y;
      });
      avgX /= nodes.length;
      avgY /= nodes.length;
      return {
        x: avgX,
        y: avgY
      };
    },

    groupNodes: function(currentModel, selectedNodes) {
      const selectedNodeIds = [];
      selectedNodes.forEach(selectedNode => {
        selectedNodeIds.push(selectedNode.getNodeId());
      });

      const brotherNodes = this.__getBrotherNodes(currentModel, selectedNodeIds);

      // Create nodesGroup
      const nodesGroupService = osparc.utils.Services.getNodesGroup();
      const parentNode = currentModel.getNodeId ? currentModel : null;
      const nodesGroup = this.createNode(nodesGroupService.key, nodesGroupService.version, null, parentNode);
      if (!nodesGroup) {
        return;
      }

      const avgPos = this.__getAveragePosition(selectedNodes);
      nodesGroup.setPosition(avgPos);

      // change parents on future inner nodes
      selectedNodes.forEach(selectedNode => {
        this.moveNode(selectedNode, nodesGroup, parentNode);
      });

      // find inputNodes for nodesGroup
      selectedNodes.forEach(selectedNode => {
        const selInputNodes = selectedNode.getInputNodes();
        selInputNodes.forEach(inputNode => {
          const index = selectedNodeIds.indexOf(inputNode);
          if (index === -1) {
            nodesGroup.addInputNode(inputNode);
          }
        });
      });

      // change input nodes in those nodes connected to the selected ones
      brotherNodes.forEach(brotherNode => {
        selectedNodes.forEach(selectedNode => {
          const selectedNodeId = selectedNode.getNodeId();
          if (brotherNode.isInputNode(selectedNodeId)) {
            brotherNode.addInputNode(nodesGroup.getNodeId());
            brotherNode.removeInputNode(selectedNodeId);
            nodesGroup.addOutputNode(selectedNodeId);
          }
        });
      });

      // update output nodes list
      if (currentModel.isContainer()) {
        selectedNodes.forEach(selectedNode => {
          const selectedNodeId = selectedNode.getNodeId();
          if (currentModel.isOutputNode(selectedNodeId)) {
            currentModel.removeOutputNode(selectedNodeId);
            nodesGroup.addOutputNode(selectedNodeId);
            currentModel.addOutputNode(nodesGroup.getNodeId());
          }
        });
      }
    },

    ungroupNode: function(currentModel, nodesGroup) {
      let newParentNode = null;
      if (currentModel !== this) {
        newParentNode = currentModel;
      }

      const brotherNodes = this.__getBrotherNodes(currentModel, [nodesGroup.getNodeId()]);


      // change parents on old inner nodes
      const innerNodes = nodesGroup.getInnerNodes(false);
      for (const innerNodeId in innerNodes) {
        const innerNode = innerNodes[innerNodeId];
        this.moveNode(innerNode, newParentNode, nodesGroup);
      }

      // change input nodes in those nodes connected to the nodesGroup
      brotherNodes.forEach(brotherNode => {
        if (brotherNode.isInputNode(nodesGroup.getNodeId())) {
          brotherNode.removeInputNode(nodesGroup.getNodeId());
          brotherNode.addInputNodes(nodesGroup.getOutputNodes());

          if (brotherNode.isContainer()) {
            const broInnerNodes = Object.values(brotherNode.getInnerNodes(true));
            broInnerNodes.forEach(broInnerNode => {
              if (broInnerNode.isInputNode(nodesGroup.getNodeId())) {
                broInnerNode.removeInputNode(nodesGroup.getNodeId());
                broInnerNode.addInputNodes(nodesGroup.getOutputNodes());
              }
            });
          }
        }
      });

      // update output nodes list
      if (currentModel.isContainer()) {
        if (currentModel.isOutputNode(nodesGroup.getNodeId())) {
          currentModel.removeOutputNode(nodesGroup.getNodeId());
          currentModel.addOutputNodes(nodesGroup.getOutputNodes());
        }
      }

      // Remove nodesGroup
      this.removeNode(nodesGroup.getNodeId());
    },

    serialize: function() {
      if (this.__workbenchInitData !== null) {
        // workbench is not initialized
        return this.__workbenchInitData;
      }
      let workbench = {};
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        const data = node.serialize();
        if (data) {
          workbench[node.getNodeId()] = data;
        }
      }
      return workbench;
    },

    serializeUI: function() {
      if (this.__workbenchUIInitData !== null) {
        // workbenchUI is not initialized
        return this.__workbenchUIInitData;
      }
      let workbenchUI = {};
      const nodes = this.getNodes(true);
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        workbenchUI[nodeId] = {};
        workbenchUI[nodeId]["position"] = node.getPosition();
      }
      return workbenchUI;
    }
  }
});
