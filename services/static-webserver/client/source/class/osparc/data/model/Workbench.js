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
    "pipelineChanged": "qx.event.type.Event",
    "reloadModel": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Data",
    "fileRequested": "qx.event.type.Data",
    "openNode": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false,
      event: "changeStudy"
    }
  },

  members: {
    __workbenchInitData: null,
    __workbenchUIInitData: null,
    __rootNodes: null,
    __edges: null,

    getWorkbenchInitData: function() {
      return this.__workbenchInitData;
    },

    // deserializes the workbenchInitData
    buildWorkbench: function() {
      this.__rootNodes = {};
      this.__edges = {};
      this.__deserialize(this.__workbenchInitData, this.__workbenchUIInitData);
      this.__workbenchInitData = null;
      this.__workbenchUIInitData = null;
    },

    // starts the dynamic services
    initWorkbench: function() {
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      nodes.forEach(node => node.startDynamicService());
    },

    getUpstreamCompNodes: function(node, recursive = true, upstreamNodes = new Set()) {
      const links = node.getLinks();
      links.forEach(link => {
        upstreamNodes.add(link["nodeUuid"]);
        if (recursive) {
          const linkNode = this.getNode(link["nodeUuid"]);
          if (linkNode.isComputational()) {
            this.getUpstreamCompNodes(linkNode, recursive, upstreamNodes);
          }
        }
      });
      return Array.from(upstreamNodes).reverse();
    },

    isPipelineLinear: function() {
      const nodes = this.getNodes(true);
      const inputNodeIds = [];
      const nodesWithoutInputs = [];
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        const inputNodes = node.getInputNodes();
        if (inputNodes.length === 0) {
          nodesWithoutInputs.push(nodeId);
        } else if (inputNodes.length > 1) {
          return false;
        } else {
          inputNodeIds.push(...inputNodes);
        }
      }
      // if duplicates exist, it means that there is a branching
      const duplicateExists = new Set(inputNodeIds).size !== inputNodeIds.length;
      if (duplicateExists) {
        return false;
      }

      // Make sure there are no more than one upstreams nodes
      return nodesWithoutInputs.length < 2;
    },

    getPipelineLinearSorted: function() {
      if (!this.isPipelineLinear()) {
        return null;
      }

      const sortedPipeline = [];
      const nodes = this.getNodes(true);
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        const inputNodes = node.getInputNodes();
        if (inputNodes.length === 0) {
          // first node
          sortedPipeline.splice(0, 0, nodeId);
        } else {
          // insert right after its input node
          const idx = sortedPipeline.indexOf(inputNodes[0]);
          sortedPipeline.splice(idx+1, 0, nodeId);
        }
      }
      return sortedPipeline;
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
      const study = this.getStudy();
      if (study === null) {
        return [];
      }
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

    createEdge: function(edgeId, nodeLeftId, nodeRightId, autoConnect = true) {
      const existingEdge = this.getEdge(edgeId, nodeLeftId, nodeRightId);
      if (existingEdge) {
        return existingEdge;
      }
      if (!osparc.data.Permissions.getInstance().canDo("study.edge.create", true)) {
        return null;
      }
      const nodeLeft = this.getNode(nodeLeftId);
      const nodeRight = this.getNode(nodeRightId);
      if (nodeLeft && nodeRight) {
        const edge = new osparc.data.model.Edge(edgeId, nodeLeft, nodeRight);
        this.addEdge(edge);

        if (autoConnect) {
          nodeRight.createAutoPortConnection(nodeLeft, nodeRight);
        }

        nodeRight.addInputNode(nodeLeftId);

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

      const nodeLeft = this.getNode(node1Id);
      const nodeRight = this.getNode(node2Id);
      nodeLeft.setOutputConnected(true);
      nodeRight.setInputConnected(true);
    },

    __createNode: function(study, key, version, uuid) {
      osparc.utils.Utils.localCache.serviceToFavs(key);
      const node = new osparc.data.model.Node(study, key, version, uuid);
      node.addListener("keyChanged", () => this.fireEvent("reloadModel"), this);
      node.addListener("changeInputNodes", () => this.fireDataEvent("pipelineChanged"), this);
      node.addListener("reloadModel", () => this.fireEvent("reloadModel"), this);
      return node;
    },

    createNode: function(key, version, uuid, parent) {
      const existingNode = this.getNode(uuid);
      if (existingNode) {
        return existingNode;
      }
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        return null;
      }

      const node = this.__createNode(this.getStudy(), key, version, uuid);
      this.addNode(node, parent);

      this.__initNodeSignals(node);

      node.populateNodeData();
      this.giveUniqueNameToNode(node, node.getLabel());
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
        node.addListener("showInLogger", e => this.fireDataEvent("showInLogger", e.getData()), this);
        node.addListener("retrieveInputs", e => this.fireDataEvent("retrieveInputs", e.getData()), this);
        node.addListener("fileRequested", e => this.fireDataEvent("fileRequested", e.getData()), this);
        node.addListener("filePickerRequested", e => {
          const {
            portId,
            nodeId,
            file
          } = e.getData();
          this.__filePickerNodeRequested(nodeId, portId, file);
        }, this);
        node.addListener("parameterRequested", e => {
          const {
            portId,
            nodeId
          } = e.getData();
          this.__parameterNodeRequested(nodeId, portId);
        }, this);
        node.addListener("probeRequested", e => {
          const {
            portId,
            nodeId
          } = e.getData();
          this.__probeNodeRequested(nodeId, portId);
        }, this);
      }
    },

    getFreePosition: function(node, toTheLeft = true) {
      // do not overlap the new node2 with other nodes
      const pos = node.getPosition();
      const nodeWidth = osparc.component.workbench.NodeUI.NODE_WIDTH;
      const nodeHeight = osparc.component.workbench.NodeUI.NODE_HEIGHT;
      const xPos = toTheLeft ? Math.max(0, pos.x-nodeWidth-30) : pos.x+nodeWidth+30;
      let yPos = pos.y;
      const allNodes = this.getNodes();
      const avoidY = [];
      for (const nId in allNodes) {
        const node2 = allNodes[nId];
        if (node2.getPosition().x >= xPos-nodeWidth && node2.getPosition().x <= (xPos+nodeWidth)) {
          avoidY.push(node2.getPosition().y);
        }
      }
      avoidY.sort((a, b) => a - b); // For ascending sort
      avoidY.forEach(y => {
        if (yPos >= y-nodeHeight && yPos <= (y+nodeHeight)) {
          yPos = y+nodeHeight+20;
        }
      });

      return {
        x: xPos,
        y: yPos
      };
    },

    getFarthestPosition: function() {
      let x = 0;
      let y = 0;
      Object.values(this.getNodes()).forEach(node => {
        x = Math.max(x, node.getPosition().x);
        y = Math.max(y, node.getPosition().y);
      });
      x += osparc.component.workbench.NodeUI.NODE_WIDTH;
      y += osparc.component.workbench.NodeUI.NODE_HEIGHT;
      return {
        x,
        y
      };
    },

    __connectFilePicker: function(nodeId, portId) {
      return new Promise((resolve, reject) => {
        const requesterNode = this.getNode(nodeId);
        const freePos = this.getFreePosition(requesterNode);

        // create a new FP
        const filePickerMetadata = osparc.utils.Services.getFilePicker();
        const filePicker = this.createNode(filePickerMetadata["key"], filePickerMetadata["version"]);
        filePicker.setPosition(freePos);

        // create connection
        const filePickerId = filePicker.getNodeId();
        requesterNode.addInputNode(filePickerId);
        // reload also before port connection happens
        this.fireEvent("reloadModel");
        requesterNode.addPortLink(portId, filePickerId, "outFile")
          .then(success => {
            if (success) {
              resolve(filePicker);
            } else {
              this.removeNode(filePickerId);
              const msg = qx.locale.Manager.tr("File couldn't be assigned");
              osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
              reject();
            }
          });
      });
    },

    __filePickerNodeRequested: function(nodeId, portId, file) {
      this.__connectFilePicker(nodeId, portId)
        .then(filePicker => {
          if (file) {
            const fileObj = file.data;
            osparc.file.FilePicker.setOutputValueFromStore(
              filePicker,
              fileObj.getLocation(),
              fileObj.getDatasetId(),
              fileObj.getFileId(),
              fileObj.getLabel()
            );
          }
          this.fireDataEvent("openNode", filePicker.getNodeId());
          this.fireEvent("reloadModel");
        });
    },

    __parameterNodeRequested: function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ParameterNode
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetaData()["inputs"], portId);
      const pmMD = osparc.utils.Services.getParameterMetadata(type);
      if (pmMD) {
        const pm = this.createNode(pmMD["key"], pmMD["version"]);

        // do not overlap the new Parameter Node with other nodes
        const freePos = this.getFreePosition(requesterNode);
        pm.setPosition(freePos);

        // create connection
        const pmId = pm.getNodeId();
        requesterNode.addInputNode(pmId);
        // bypass the compatibility check
        if (requesterNode.getPropsForm().addPortLink(portId, pmId, "out_1") !== true) {
          this.removeNode(pmId);
          const msg = qx.locale.Manager.tr("Parameter couldn't be assigned");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        }
        this.fireEvent("reloadModel");
      }
    },

    __probeNodeRequested: function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ProbeNode
      const requesterPortMD = requesterNode.getMetaData()["outputs"][portId];
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetaData()["outputs"], portId);
      const probeMD = osparc.utils.Services.getProbeMetadata(type);
      if (probeMD) {
        const probeNode = this.createNode(probeMD["key"], probeMD["version"]);
        probeNode.setLabel(requesterPortMD.label);

        // do not overlap the new Parameter Node with other nodes
        const freePos = this.getFreePosition(requesterNode, false);
        probeNode.setPosition(freePos);

        // create connection
        const probeId = probeNode.getNodeId();
        probeNode.addInputNode(nodeId);
        // bypass the compatibility check
        if (probeNode.getPropsForm().addPortLink("in_1", nodeId, portId) !== true) {
          this.removeNode(probeId);
          const msg = qx.locale.Manager.tr("Probe couldn't be assigned");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        }
        this.fireEvent("reloadModel");
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
      this.fireEvent("pipelineChanged");
    },

    removeNode: function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.delete", true)) {
        return false;
      }

      // remove first the connected edges
      const connectedEdges = this.getConnectedEdges(nodeId);
      connectedEdges.forEach(connectedEdgeId => {
        this.removeEdge(connectedEdgeId);
      });

      let node = this.getNode(nodeId);
      if (node) {
        node.removeNode();

        const isTopLevel = Object.prototype.hasOwnProperty.call(this.__rootNodes, nodeId);
        if (isTopLevel) {
          delete this.__rootNodes[nodeId];
        }

        // remove it from slideshow
        if (this.getStudy()) {
          this.getStudy().getUi().getSlideshow()
            .removeNode(nodeId);
        }

        this.fireEvent("pipelineChanged");
        return true;
      }
      return false;
    },

    addServiceBetween: function(service, leftNodeId, rightNodeId) {
      // create node
      const node = this.createNode(service.getKey(), service.getVersion());
      if (!node) {
        return null;
      }
      if (leftNodeId) {
        const leftNode = this.getNode(leftNodeId);
        node.setPosition(this.getFreePosition(leftNode, false));
      } else if (rightNodeId) {
        const rightNode = this.getNode(rightNodeId);
        node.setPosition(this.getFreePosition(rightNode, true));
      } else {
        node.setPosition({
          x: 20,
          y: 20
        });
      }

      // break previous connection
      if (leftNodeId && rightNodeId) {
        const edge = this.getEdge(null, leftNodeId, rightNodeId);
        if (edge) {
          this.removeEdge(edge.getEdgeId());
        }
      }

      // create connections
      if (leftNodeId) {
        this.createEdge(null, leftNodeId, node.getNodeId(), true);
      }
      if (rightNodeId) {
        this.createEdge(null, node.getNodeId(), rightNodeId, true);
      }
      this.fireEvent("reloadModel");

      return node;
    },

    removeEdge: function(edgeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.edge.delete", true)) {
        return false;
      }

      const edge = this.getEdge(edgeId);
      if (edge) {
        const inputNodeId = edge.getInputNodeId();
        const outputNodeId = edge.getOutputNodeId();
        const node = this.getNode(outputNodeId);
        if (node) {
          node.removeInputNode(inputNodeId);
          node.removeNodePortConnections(inputNodeId);
          delete this.__edges[edgeId];

          const edges = Object.values(this.__edges);
          if (edges.findIndex(edg => edg.getInputNodeId() === inputNodeId) === -1) {
            const nodeLeft = this.getNode(inputNodeId);
            nodeLeft.setOutputConnected(false);
          }
          if (edges.findIndex(edg => edg.getOutputNodeId() === outputNodeId) === -1) {
            const nodeRight = this.getNode(outputNodeId);
            nodeRight.setInputConnected(false);
          }

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
        const node = this.__createNode(this.getStudy(), nodeData.key, nodeData.version, nodeId);
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
        const node = this.getNode(nodeId);
        this.giveUniqueNameToNode(node, node.getLabel());
      });
    },

    giveUniqueNameToNode: function(node, label, suffix = 2) {
      const newLabel = label + "_" + suffix;
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node2 of nodes) {
        if (node2.getNodeId() !== node.getNodeId() &&
            node2.getLabel().localeCompare(node.getLabel()) === 0) {
          node.setLabel(newLabel);
          this.giveUniqueNameToNode(node, label, suffix+1);
        }
      }
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

    serialize: function(clean = true) {
      if (this.__workbenchInitData !== null) {
        // workbench is not initialized
        return this.__workbenchInitData;
      }
      let workbench = {};
      const allModels = this.getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        const data = node.serialize(clean);
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
        const marker = node.getMarker();
        if (marker) {
          workbenchUI[nodeId]["marker"] = {
            color: marker.getColor()
          };
        }
      }
      return workbenchUI;
    }
  }
});
