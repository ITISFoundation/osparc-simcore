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
    "restartAutoSaveTimer": "qx.event.type.Event",
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

    __createNode: function(study, metadata, uuid) {
      osparc.utils.Utils.localCache.serviceToFavs(metadata.key);
      const node = new osparc.data.model.Node(study, metadata, uuid);
      node.addListener("keyChanged", () => this.fireEvent("reloadModel"), this);
      node.addListener("changeInputNodes", () => this.fireDataEvent("pipelineChanged"), this);
      node.addListener("reloadModel", () => this.fireEvent("reloadModel"), this);
      node.addListener("updateStudyDocument", () => this.fireEvent("updateStudyDocument"), this);
      return node;
    },

    createNode: async function(key, version) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.create", true)) {
        osparc.FlashMessenger.getInstance().logAs(qx.locale.Manager.tr("You are not allowed to add nodes"), "ERROR");
        return null;
      }
      if (this.getStudy().isPipelineRunning()) {
        osparc.FlashMessenger.getInstance().logAs(this.self().CANT_ADD_NODE, "ERROR");
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
        const metadata = await osparc.store.Services.getService(key, version);
        const resp = await osparc.data.Resources.fetch("studies", "addNode", params);
        const nodeId = resp["node_id"];

        this.fireEvent("restartAutoSaveTimer");
        const node = this.__createNode(this.getStudy(), metadata, nodeId);
        this.__initNodeSignals(node);
        this.__addNode(node);

        node.populateNodeData();
        this.giveUniqueNameToNode(node, node.getLabel());
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
        osparc.FlashMessenger.getInstance().logAs(errorMsg, "ERROR");
        return null;
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
      }
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
      const filePickerMetadata = osparc.service.Utils.getFilePicker();
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
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
          }
        });
    },

    __parameterNodeRequested: async function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ParameterNode
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetaData()["inputs"], portId);
      const parameterMetadata = osparc.service.Utils.getParameterMetadata(type);
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
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        }
        this.fireEvent("reloadModel");
      }
    },

    __probeNodeRequested: async function(nodeId, portId) {
      const requesterNode = this.getNode(nodeId);

      // create a new ProbeNode
      const requesterPortMD = requesterNode.getMetaData()["outputs"][portId];
      const type = osparc.utils.Ports.getPortType(requesterNode.getMetaData()["outputs"], portId);
      const probeMetadata = osparc.service.Utils.getProbeMetadata(type);
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
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        }
        this.fireEvent("reloadModel");
      }
    },

    __addNode: function(node) {
      const nodeId = node.getNodeId();
      this.__nodes[nodeId] = node;
      this.fireEvent("pipelineChanged");
    },

    removeNode: async function(nodeId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.delete", true)) {
        return false;
      }
      if (this.getStudy().isPipelineRunning()) {
        osparc.FlashMessenger.getInstance().logAs(this.self().CANT_DELETE_NODE, "ERROR");
        return false;
      }

      let node = this.getNode(nodeId);
      if (node) {
        this.fireEvent("restartAutoSaveTimer");
        // remove the node in the backend first
        const removed = await node.removeNode();
        if (removed) {
          this.fireEvent("restartAutoSaveTimer");

          delete this.__nodes[nodeId];

          // remove first the connected edges
          const connectedEdges = this.getConnectedEdges(nodeId);
          connectedEdges.forEach(connectedEdgeId => {
            this.removeEdge(connectedEdgeId);
          });

          // remove it from ui model
          if (this.getStudy()) {
            this.getStudy().getUi().removeNode(nodeId);
          }

          this.fireEvent("pipelineChanged");
          return true;
        }
      }
      return false;
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
          rightNode.removeInputNode(leftNodeId);
          rightNode.removeNodePortConnections(leftNodeId);
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

    giveUniqueNameToNode: function(node, label, suffix = 2) {
      const newLabel = label + "_" + suffix;
      const allModels = this.getNodes();
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
          // old way for storing the position
          this.getNode(nodeId).populateNodeUIData(nodeData);
        }
        if (workbenchUIData && "workbench" in workbenchUIData && nodeId in workbenchUIData.workbench) {
          this.getNode(nodeId).populateNodeUIData(workbenchUIData.workbench[nodeId]);
        }
      });
    },

    __deserialize: function(workbenchInitData, workbenchUIInitData) {
      this.__deserializeNodes(workbenchInitData, workbenchUIInitData)
        .then(() => {
          this.__deserializeEdges(workbenchInitData);
          workbenchInitData = null;
          workbenchUIInitData = null;
          this.setDeserialized(true);
        });
    },

    __deserializeNodes: function(workbenchData, workbenchUIData = {}) {
      const nodeIds = Object.keys(workbenchData);

      const metadataPromises = [];
      nodeIds.forEach(nodeId => {
        const nodeData = workbenchData[nodeId];
        metadataPromises.push(osparc.store.Services.getService(nodeData.key, nodeData.version));
      });

      return Promise.all(metadataPromises)
        .then(values => {
          // Create first all the nodes
          for (let i=0; i<nodeIds.length; i++) {
            const metadata = values[i];
            const nodeId = nodeIds[i];
            const node = this.__createNode(this.getStudy(), metadata, nodeId);
            this.__initNodeSignals(node);
            this.__addNode(node);
          }

          // Then populate them (this will avoid issues of connecting nodes that might not be created yet)
          this.__populateNodesData(workbenchData, workbenchUIData);

          nodeIds.forEach(nodeId => {
            const node = this.getNode(nodeId);
            this.giveUniqueNameToNode(node, node.getLabel());
          });
        });
    },

    __deserializeEdges: function(workbenchData) {
      for (const nodeId in workbenchData) {
        const nodeData = workbenchData[nodeId];
        const node = this.getNode(nodeId);
        if (node === null) {
          continue;
        }
        this.__addInputOutputNodesAndEdges(node, nodeData.inputNodes);
      }
    },

    __addInputOutputNodesAndEdges: function(node, inputOutputNodeIds) {
      if (inputOutputNodeIds) {
        inputOutputNodeIds.forEach(inputOutputNodeId => {
          const node1 = this.getNode(inputOutputNodeId);
          if (node1 === null) {
            return;
          }
          const edge = new osparc.data.model.Edge(null, node1, node);
          this.addEdge(edge);
          node.addInputNode(inputOutputNodeId);
        });
      }
    },

    serialize: function(clean = true) {
      if (this.__workbenchInitData !== null) {
        // workbench is not initialized
        return this.__workbenchInitData;
      }
      let workbench = {};
      const allModels = this.getNodes();
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
      const nodes = this.getNodes();
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
    },

    /**
     * Call patch Node, but the changes were already applied on the frontend
     * @param workbenchDiffs {Object} Diff Object coming from the JsonDiffPatch lib. Use only the keys, not the changes.
     */
    patchWorkbenchDelayed: function(workbenchDiffs) {
      const promises = [];
      Object.keys(workbenchDiffs).forEach(nodeId => {
        const node = this.getNode(nodeId);
        if (node === null) {
          // the node was removed
          return;
        }

        const nodeData = node.serialize();
        let patchData = {};
        if (workbenchDiffs[nodeId] instanceof Array) {
          // if workbenchDiffs is an array means that the node was either added or removed
          // the node was added
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
    }
  }
});
