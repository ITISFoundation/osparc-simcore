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
 *   const workbench = new osparc.data.model.Workbench(study.workbench, study.workbenchUI)
 *   study.setWorkbench(workbench);
 *   workbench.initWorkbench();
 * </pre>
 */

qx.Class.define("osparc.data.model.Workbench", {
  extend: qx.core.Object,

  /**
    * @param workbenchData {Object} Object containing the workbench raw data
    * @param workbenchUIData {Object} Object containing the workbenchUI raw data
    */
  construct: function(workbenchData, workbenchUIData = null) {
    this.base(arguments);

    this.__workbenchInitData = workbenchData;
    this.__workbenchUIInitData = workbenchUIData;
  },

  events: {
    "updateStudyDocument": "qx.event.type.Event",
    "projectDocumentChanged": "qx.event.type.Data",
    "restartAutoSaveTimer": "qx.event.type.Event",
    "pipelineChanged": "qx.event.type.Event",
    "nodeAdded": "qx.event.type.Data",
    "nodeRemoved": "qx.event.type.Data",
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
    },

    deserialized: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeDeserialized"
    }
  },

  statics: {
    CANT_ADD_NODE: qx.locale.Manager.tr("Nodes can't be added while the pipeline is running"),
    CANT_DELETE_NODE: qx.locale.Manager.tr("Nodes can't be deleted while the pipeline is running"),

    getLinkedNodeIds: function(workbenchData) {
      const linkedNodeIDs = new Set([]);
      Object.values(workbenchData).forEach(nodeData => {
        const linkedNodes = osparc.data.model.Node.getLinkedNodeIds(nodeData);
        linkedNodes.forEach(linkedNodeID => linkedNodeIDs.add(linkedNodeID))
      });
      return Array.from(linkedNodeIDs);
    },
  },

  members: {
    __workbenchInitData: null,
    __workbenchUIInitData: null,
    __nodes: null,
    __edges: null,

    getWorkbenchInitData: function() {
      return this.__workbenchInitData;
    },

    // deserializes the workbenchInitData
    buildWorkbench: function() {
      this.__nodes = {};
      this.__edges = {};
      this.__deserialize(this.__workbenchInitData, this.__workbenchUIInitData);
      this.__workbenchInitData = null;
      this.__workbenchUIInitData = null;
    },

    __deserialize: function(workbenchInitData, uiData = {}) {
      const nodeDatas = {};
      const nodeUiDatas = {};
      for (const nodeId in workbenchInitData) {
        const nodeData = workbenchInitData[nodeId];
        nodeDatas[nodeId] = nodeData;
        if (uiData["workbench"] && nodeId in uiData["workbench"]) {
          nodeUiDatas[nodeId] = uiData["workbench"][nodeId];
        }
      }
      this.__deserializeNodes(nodeDatas, nodeUiDatas)
        .then(() => {
          this.__deserializeEdges(workbenchInitData);
          this.setDeserialized(true);
        });
    },

    __deserializeNodes: function(nodeDatas, nodeUiDatas) {
      const nodesPromises = [];
      for (const nodeId in nodeDatas) {
        const nodeData = nodeDatas[nodeId];
        const nodeUiData = nodeUiDatas[nodeId];
        const node = this.__createNode(nodeData["key"], nodeData["version"], nodeId);
        nodesPromises.push(node.fetchMetadataAndPopulate(nodeData, nodeUiData));
      }
      return Promise.allSettled(nodesPromises);
    },

    __createNode: function(key, version, nodeId) {
      const node = new osparc.data.model.Node(this.getStudy(), key, version, nodeId);
      this.__addNode(node);
      this.__initNodeSignals(node);
      osparc.utils.Utils.localCache.serviceToFavs(key);
      return node;
    },


    __deserializeEdges: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const node = this.getNode(nodeId);
        if (node === null) {
          continue;
        }
        const nodeData = workbenchData[nodeId];
        const inputNodeIds = nodeData.inputNodes || [];
        inputNodeIds.forEach(inputNodeId => {
          const inputNode = this.getNode(inputNodeId);
          if (inputNode === null) {
            return;
          }
          const edge = new osparc.data.model.Edge(null, inputNode, node);
          this.addEdge(edge);
          node.addInputNode(inputNodeId);
        });
      }
    },

    // starts the dynamic services
    initWorkbench: function() {
      const allModels = this.getNodes();
      const nodes = Object.values(allModels);
      nodes.forEach(node => node.checkState());
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

    __getDownstreamNodes: function(node) {
      const downstreamNodes = [];
      Object.values(this.getNodes()).forEach(n => {
        const inputNodes = n.getInputNodes();
        if (inputNodes.includes(node.getNodeId())) {
          downstreamNodes.push(n);
        }
      });
      return downstreamNodes;
    },

    isPipelineLinear: function() {
      const nodes = this.getNodes();
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

      // Make sure there are no more than one upstream nodes
      return nodesWithoutInputs.length < 2;
    },

    getPipelineLinearSorted: function() {
      if (!this.isPipelineLinear()) {
        return null;
      }

      const sortedPipeline = [];
      const nodes = this.getNodes();
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
      const allNodes = this.getNodes();
      const exists = Object.prototype.hasOwnProperty.call(allNodes, nodeId);
      if (exists) {
        return allNodes[nodeId];
      }
      return null;
    },

    getNodes: function() {
      let nodes = Object.assign({}, this.__nodes);
      return nodes;
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

    createUnknownNode: function(nodeId) {
      if (nodeId === undefined) {
        nodeId = osparc.utils.Utils.uuidV4();
      }
      const node = new osparc.data.model.NodeUnknown(this.getStudy(), null, null, nodeId);
      this.__addNode(node);
      node.populateNodeData();
      return node;
    },

    createNode: async function(key, version) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        const msg = qx.locale.Manager.tr("You are not allowed to add nodes");
        osparc.FlashMessenger.logError(msg);
        return null;
      }
      if (this.getStudy().isPipelineRunning()) {
        osparc.FlashMessenger.logError(this.self().CANT_ADD_NODE);
        return null;
      }

      this.fireEvent("restartAutoSaveTimer");
      // create the node in the backend first
      const params = {
        url: {
          studyId: this.getStudy().getUuid()
        },
        data: {
          "service_key": key,
          "service_version": version
        }
      };

      try {
        const resp = await osparc.data.Resources.fetch("studies", "addNode", params);
        const nodeId = resp["node_id"];

        this.fireEvent("restartAutoSaveTimer");
        const node = this.__createNode(key, version, nodeId);
        node.fetchMetadataAndPopulate();
        // OM here: then maybe
        this.__giveUniqueNameToNode(node, node.getLabel());
        node.checkState();

        return node;
      } catch (err) {
        let errorMsg = "";
        if ("status" in err && err.status === 406) {
          errorMsg = key + ":" + version + qx.locale.Manager.tr(" is retired");
        } else {
          errorMsg = err.message || qx.locale.Manager.tr("Error creating ") + key + ":" + version;
        }
        const errorMsgData = {
          msg: errorMsg,
          level: "ERROR"
        };
        this.fireDataEvent("showInLogger", errorMsgData);
        osparc.FlashMessenger.logError(errorMsg);
        return null;
      }
    },

    __initNodeSignals: function(node) {
      if (osparc.utils.Utils.eventDrivenPatch()) {
        node.listenToChanges();
        node.addListener("projectDocumentChanged", e => this.fireDataEvent("projectDocumentChanged", e.getData()), this);
      }
      node.addListener("keyChanged", () => this.fireEvent("reloadModel"), this);
      node.addListener("changeInputNodes", () => this.fireDataEvent("pipelineChanged"), this);
      node.addListener("reloadModel", () => this.fireEvent("reloadModel"), this);
      node.addListener("updateStudyDocument", () => this.fireEvent("updateStudyDocument"), this);

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
      node.addListener("fileUploaded", () => {
        // downstream nodes might have started downloading file picker's output.
        // show feedback to the user
        const downstreamNodes = this.__getDownstreamNodes(node);
        downstreamNodes.forEach(downstreamNode => {
          downstreamNode.getPortIds().forEach(portId => {
            const link = downstreamNode.getLink(portId);
            if (link && link["nodeUuid"] === node.getNodeId() && link["output"] === "outFile") {
              // connected to file picker's output
              setTimeout(() => {
                // start retrieving state after 2"
                downstreamNode.retrieveInputs(portId);
              }, 2000);
            }
          });
        });
      }, this);
    },

    getFreePosition: function(node, toTheLeft = true) {
      // do not overlap the new node2 with other nodes
      const pos = node.getPosition();
      const nodeWidth = osparc.workbench.NodeUI.NODE_WIDTH;
      const nodeHeight = osparc.workbench.NodeUI.NODE_HEIGHT;
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
      x += osparc.workbench.NodeUI.NODE_WIDTH;
      y += osparc.workbench.NodeUI.NODE_HEIGHT;
      return {
        x,
        y
      };
    },

    __filePickerNodeRequested: async function(nodeId, portId, file) {
      const filePickerMetadata = osparc.store.Services.getFilePicker();
      const filePicker = await this.createNode(filePickerMetadata["key"], filePickerMetadata["version"]);
      if (filePicker === null) {
        return;
      }

      const requesterNode = this.getNode(nodeId);
      const freePos = this.getFreePosition(requesterNode);
      filePicker.setPosition(freePos);

      // create connection
      const filePickerId = filePicker.getNodeId();
      requesterNode.addInputNode(filePickerId);
      // reload also before port connection happens
      this.fireEvent("reloadModel");
      requesterNode.addPortLink(portId, filePickerId, "outFile")
        .then(success => {
          if (success) {
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
          } else {
            this.removeNode(filePickerId);
            const msg = qx.locale.Manager.tr("File couldn't be assigned");
            osparc.FlashMessenger.logError(msg);
          }
        });
    },

    __parameterNodeRequested: async function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ParameterNode
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetadata()["inputs"], portId);
      const parameterMetadata = osparc.store.Services.getParameterMetadata(type);
      if (parameterMetadata) {
        const parameterNode = await this.createNode(parameterMetadata["key"], parameterMetadata["version"]);
        if (parameterNode === null) {
          return;
        }

        // do not overlap the new Parameter Node with other nodes
        const freePos = this.getFreePosition(requesterNode);
        parameterNode.setPosition(freePos);

        // create connection
        const pmId = parameterNode.getNodeId();
        requesterNode.addInputNode(pmId);
        // bypass the compatibility check
        if (requesterNode.getPropsForm().addPortLink(portId, pmId, "out_1") !== true) {
          this.removeNode(pmId);
          const msg = qx.locale.Manager.tr("Parameter couldn't be assigned");
          osparc.FlashMessenger.logError(msg);
        }
        this.fireEvent("reloadModel");
      }
    },

    __probeNodeRequested: async function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ProbeNode
      const requesterPortMD = requesterNode.getMetadata()["outputs"][portId];
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetadata()["outputs"], portId);
      const probeMetadata = osparc.store.Services.getProbeMetadata(type);
      if (probeMetadata) {
        const probeNode = await this.createNode(probeMetadata["key"], probeMetadata["version"]);
        if (probeNode === null) {
          return;
        }

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
          osparc.FlashMessenger.logError(msg);
        }
        this.fireEvent("reloadModel");
      }
    },

    __addNode: function(node) {
      const nodeId = node.getNodeId();
      this.__nodes[nodeId] = node;
      const nodeAdded = () => {
        this.fireEvent("pipelineChanged");
      };
      if (node.getMetadata()) {
        nodeAdded();
      } else {
        node.addListenerOnce("changeMetadata", () => nodeAdded(), this);
      }
    },

    removeNode: async function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.delete", true)) {
        return;
      }
      if (this.getStudy().isPipelineRunning()) {
        osparc.FlashMessenger.logAs(this.self().CANT_DELETE_NODE, "ERROR");
        return;
      }

      this.fireEvent("restartAutoSaveTimer");
      let node = this.getNode(nodeId);
      if (node) {
        // remove the node in the backend first
        const removed = await node.removeNode();
        if (removed) {
          this.__nodeRemoved(nodeId);
        }
      }
    },

    __nodeRemoved: function(nodeId) {
      this.fireEvent("restartAutoSaveTimer");

      delete this.__nodes[nodeId];

      // remove first the connected edges
      const connectedEdgeIds = this.getConnectedEdges(nodeId);
      connectedEdgeIds.forEach(connectedEdgeId => {
        this.removeEdge(connectedEdgeId);
      });

      // remove it from ui model
      if (this.getStudy()) {
        this.getStudy().getUi().removeNode(nodeId);
      }

      this.fireEvent("pipelineChanged");

      this.fireDataEvent("nodeRemoved", {
        nodeId,
        connectedEdgeIds,
      });
    },

    addServiceBetween: async function(service, leftNodeId, rightNodeId) {
      // create node
      const node = await this.createNode(service.getKey(), service.getVersion());
      if (node === null) {
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
        const rightNodeId = edge.getOutputNodeId();
        const leftNodeId = edge.getInputNodeId();

        const rightNode = this.getNode(rightNodeId);
        if (rightNode) {
          // no need to make any changes to a just removed node (it would trigger a patch call)
          // first remove the port connections
          rightNode.removeNodePortConnections(leftNodeId);
          // then the node connection
          rightNode.removeInputNode(leftNodeId);
        }

        delete this.__edges[edgeId];

        // update the port decorations (remove dot if there are no more connections)
        const edges = Object.values(this.__edges);
        if (edges.findIndex(edg => edg.getInputNodeId() === leftNodeId) === -1) {
          const leftNode = this.getNode(leftNodeId);
          if (leftNode) {
            leftNode.setOutputConnected(false);
          }
        }
        if (edges.findIndex(edg => edg.getOutputNodeId() === rightNodeId) === -1) {
          if (rightNode) {
            rightNode.setInputConnected(false);
          }
        }

        return true;
      }
      return false;
    },

    __giveUniqueNameToNode: function(node, label, suffix = 2) {
      const newLabel = label + "_" + suffix;
      const allModels = this.getNodes();
      const nodes = Object.values(allModels);
      for (const node2 of nodes) {
        if (node2.getNodeId() !== node.getNodeId() &&
            node2.getLabel().localeCompare(node.getLabel()) === 0) {
          node.setLabel(newLabel);
          this.__giveUniqueNameToNode(node, label, suffix+1);
        }
      }
    },

    serialize: function() {
      if (this.__workbenchInitData !== null) {
        // workbench is not initialized
        return this.__workbenchInitData;
      }
      const workbench = {};
      const nodes = Object.values(this.getNodes());
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
      const workbenchUI = {};
      const nodes = Object.values(this.getNodes());
      for (const node of nodes) {
        const data = node.serializeUI();
        if (data) {
          workbenchUI[node.getNodeId()] = data;
        }
      }
      return workbenchUI;
    },

    /**
     * Call patch Node, but the changes were already applied on the frontend
     * @param workbenchDiffs {Object} Diff Object coming from the JsonDiffPatch lib. Use only the keys, not the changes.
     * @param workbenchSource {Object} Workbench object that was used to check the diffs on the frontend.
     */
    patchWorkbenchDiffs: function(workbenchDiffs, workbenchSource) {
      const promises = [];
      Object.keys(workbenchDiffs).forEach(nodeId => {
        const node = this.getNode(nodeId);
        if (node === null) {
          // the node was removed
          return;
        }
        // use the node data that was used to check the diffs
        const nodeData = workbenchSource[nodeId];
        if (!nodeData) {
          // skip if nodeData is undefined or null
          return;
        }

        let patchData = {};
        if (workbenchDiffs[nodeId] instanceof Array) {
          // if workbenchDiffs is an array means that the node was added
          patchData = nodeData;
        } else {
          // patch only what was changed
          Object.keys(workbenchDiffs[nodeId]).forEach(changedFieldKey => {
            if (nodeData[changedFieldKey] !== undefined) {
              // do not patch if it's undefined
              patchData[changedFieldKey] = nodeData[changedFieldKey];
            }
          });
        }
        const params = {
          url: {
            "studyId": this.getStudy().getUuid(),
            "nodeId": nodeId
          },
          data: patchData
        };
        if (Object.keys(patchData).length) {
          promises.push(osparc.data.Resources.fetch("studies", "patchNode", params));
        }
      })
      return Promise.all(promises);
    },

    /**
     * Update the workbench from the given patches.
     * @param workbenchPatches {Array} Array of workbench patches.
     * @param uiPatches {Array} Array of UI patches. They might contain info (position) about new nodes.
     */
    updateWorkbenchFromPatches: function(workbenchPatches, uiPatches) {
      // group the patches by nodeId
      const nodesAdded = [];
      const nodesRemoved = [];
      const workbenchPatchesByNode = {};
      const workbenchUiPatchesByNode = {};
      workbenchPatches.forEach(workbenchPatch => {
        const nodeId = workbenchPatch.path.split("/")[2];

        const pathParts = workbenchPatch.path.split("/");
        if (pathParts.length === 3) {
          if (workbenchPatch.op === "add") {
            // node was added
            nodesAdded.push(nodeId);
          } else if (workbenchPatch.op === "remove") {
            // node was removed
            nodesRemoved.push(nodeId);
          }
        }

        if (!(nodeId in workbenchPatchesByNode)) {
          workbenchPatchesByNode[nodeId] = [];
        }
        workbenchPatchesByNode[nodeId].push(workbenchPatch);
      });

      // first, remove nodes
      if (nodesRemoved.length) {
        this.__removeNodesFromPatches(nodesRemoved, workbenchPatchesByNode);
      }

      // second, add nodes if any
      if (nodesAdded.length) {
        // this will call update nodes once finished
        nodesAdded.forEach(nodeId => {
          const uiPatchFound = uiPatches.find(uiPatch => {
            const pathParts = uiPatch.path.split("/");
            return uiPatch.op === "add" && pathParts.length === 4 && pathParts[3] === nodeId;
          });
          if (uiPatchFound) {
            workbenchUiPatchesByNode[nodeId] = uiPatchFound;
          }
        });
        this.__addNodesFromPatches(nodesAdded, workbenchPatchesByNode, workbenchUiPatchesByNode);
      } else {
        // third, update nodes
        this.__updateNodesFromPatches(workbenchPatchesByNode);
      }
    },

    __removeNodesFromPatches: function(nodesRemoved, workbenchPatchesByNode) {
      nodesRemoved.forEach(nodeId => {
        const node = this.getNode(nodeId);

        // if the user is in that node, restore the node to the workbench
        if (this.getStudy().getUi().getCurrentNodeId() === nodeId) {
          this.getStudy().getUi().setMode("pipeline");
          this.getStudy().getUi().setCurrentNodeId(null);
        }
        if (node) {
          node.nodeRemoved(nodeId);
        }
        this.__nodeRemoved(nodeId);
        delete workbenchPatchesByNode[nodeId];
      });
    },

    __addNodesFromPatches: function(nodesAdded, workbenchPatchesByNode, workbenchUiPatchesByNode = {}) {
      nodesAdded.forEach(nodeId => {
        const addNodePatch = workbenchPatchesByNode[nodeId].find(workbenchPatch => {
          const pathParts = workbenchPatch.path.split("/");
          return pathParts.length === 3 && workbenchPatch.op === "add";
        });
        const nodeData = addNodePatch.value;
        // delete the node "add" from the workbenchPatchesByNode
        const index = workbenchPatchesByNode[nodeId].indexOf(addNodePatch);
        if (index > -1) {
          workbenchPatchesByNode[nodeId].splice(index, 1);
        }

        const nodeUiData = workbenchUiPatchesByNode[nodeId] && workbenchUiPatchesByNode[nodeId]["value"] ? workbenchUiPatchesByNode[nodeId]["value"] : {};

        const node = this.__createNode(nodeData["key"], nodeData["version"], nodeId);
        node.fetchMetadataAndPopulate(nodeData, nodeUiData)
          .then(() => {
            this.fireDataEvent("nodeAdded", node);
            node.checkState();
            // check it was already linked
            if (nodeData.inputNodes && nodeData.inputNodes.length > 0) {
              nodeData.inputNodes.forEach(inputNodeId => {
                node.fireDataEvent("edgeCreated", {
                  nodeId1: inputNodeId,
                  nodeId2: nodeId,
                });
              });
            }
          });
      });
    },

    __updateNodesFromPatches: function(workbenchPatchesByNode) {
      Object.keys(workbenchPatchesByNode).forEach(nodeId => {
        const node = this.getNode(nodeId);
        if (node === null) {
          console.warn(`Node with id ${nodeId} not found, skipping patch application.`);
          return;
        }
        const nodePatches = workbenchPatchesByNode[nodeId];
        node.updateNodeFromPatch(nodePatches);
      });
    },

    /** DEPRECATED */
    __deserializeOld: function(workbenchInitData, workbenchUIInitData) {
      this.__deserializeNodesOld(workbenchInitData, workbenchUIInitData)
        .then(() => {
          this.__deserializeEdges(workbenchInitData);
          workbenchInitData = null;
          workbenchUIInitData = null;
          this.setDeserialized(true);
        });
    },

    __deserializeNodesOld: function(workbenchData, workbenchUIData = {}) {
      const nodeIds = Object.keys(workbenchData);
      const serviceMetadataPromises = [];
      nodeIds.forEach(nodeId => {
        const nodeData = workbenchData[nodeId];
        serviceMetadataPromises.push(osparc.store.Services.getService(nodeData.key, nodeData.version));
      });
      return Promise.allSettled(serviceMetadataPromises)
        .then(results => {
          const missing = results.filter(result => result.status === "rejected" || result.value === null)
          if (missing.length) {
            const errorMsg = qx.locale.Manager.tr("Service metadata missing");
            osparc.FlashMessenger.logError(errorMsg);
            return;
          }
          const values = results.map(result => result.value);
          // Create first all the nodes
          for (let i=0; i<nodeIds.length; i++) {
            const metadata = values[i];
            const nodeId = nodeIds[i];
            this.__createNodeOld(metadata, nodeId);
          }

          // Then populate them (this will avoid issues of connecting nodes that might not be created yet)
          this.__populateNodesDataOld(workbenchData, workbenchUIData);
        });
    },

    __createNodeOld: function(metadata, nodeId) {
      const node = new osparc.data.model.Node(this.getStudy(), metadata["key"], metadata["version"], nodeId);
      node.setMetadata(metadata);
      if (osparc.utils.Utils.eventDrivenPatch()) {
        node.listenToChanges();
        node.addListener("projectDocumentChanged", e => this.fireDataEvent("projectDocumentChanged", e.getData()), this);
      }
      node.addListener("keyChanged", () => this.fireEvent("reloadModel"), this);
      node.addListener("changeInputNodes", () => this.fireDataEvent("pipelineChanged"), this);
      node.addListener("reloadModel", () => this.fireEvent("reloadModel"), this);
      node.addListener("updateStudyDocument", () => this.fireEvent("updateStudyDocument"), this);
      osparc.utils.Utils.localCache.serviceToFavs(metadata["key"]);

      this.__initNodeSignals(node);
      this.__addNode(node);

      return node;
    },

    __populateNodesDataOld: function(workbenchData, workbenchUIData) {
      Object.entries(workbenchData).forEach(([nodeId, nodeData]) => {
        this.getNode(nodeId).populateNodeData(nodeData);

        if ("position" in nodeData) {
          // old place to store the position
          this.getNode(nodeId).populateNodeUIData(nodeData);
        }
        if (workbenchUIData && "workbench" in workbenchUIData && nodeId in workbenchUIData["workbench"]) {
          // new place to store the position and marker
          this.getNode(nodeId).populateNodeUIData(workbenchUIData["workbench"][nodeId]);
        }
      });
    },
  }
});
