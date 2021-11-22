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
 * @ignore(SVGElement)
 */

/**
 *   Widget containing the layout where NodeUIs and EdgeUIs, and when the model loaded
 * is a container-node, also NodeInput and NodeOutput are rendered.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let workbenchUI = new osparc.component.workbench.WorkbenchUI();
 *   this.getRoot().add(workbenchUI);
 * </pre>
 */

const BUTTON_SIZE = 38;
const ZOOM_BUTTON_SIZE = 24;
const NODE_INPUTS_WIDTH = 210;

qx.Class.define("osparc.component.workbench.WorkbenchUI", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__nodesUI = [];
    this.__edgesUI = [];
    this.__selectedNodes = [];

    this._setLayout(new qx.ui.layout.HBox());

    this._addItemsToLayout();

    this._addEventListeners();
  },

  statics: {
    getDashedBorderSytle(isRight) {
      const side = isRight ? "right" : "left";
      const borderStyle = {};
      borderStyle["background-image"] = `linear-gradient(to bottom, #3D3D3D 50%, rgba(255, 255, 255, 0) 0%)`;
      borderStyle["background-position"] = side;
      borderStyle["background-size"] = "5px 50px";
      borderStyle["background-repeat"] = "repeat-y";
      return borderStyle;
    },

    ZOOM_VALUES: [
      0.1,
      0.2,
      0.3,
      0.4,
      0.5,
      0.7,
      0.8,
      0.9,
      1,
      1.1,
      1.2,
      1.3,
      1.5,
      2,
      2.5,
      3
    ]
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "removeEdge": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      nullable: false
    },

    scale: {
      check: "osparc.component.workbench.WorkbenchUI.ZOOM_VALUES",
      init: 1,
      apply: "__applyScale",
      event: "changeScale",
      nullable: false
    }
  },

  members: {
    _currentModel: null,
    __unlinkButton: null,
    __nodesUI: null,
    __edgesUI: null,
    __selectedNodes: null,
    __inputNodesLayout: null,
    __outputNodesLayout: null,
    __workbenchLayer: null,
    __workbenchLayout: null,
    _workbenchLayoutScroll: null,
    __desktop: null,
    __svgLayer: null,
    __tempEdgeNodeId: null,
    __tempEdgeIsInput: null,
    __tempEdgeRepr: null,
    __pointerPos: null,
    __selectedItemId: null,
    __startHint: null,
    __dropMe: null,
    __panning: null,
    __isDraggingFile: null,
    __isDraggingLink: null,

    __applyStudy: function(study) {
      study.getWorkbench().addListener("reloadModel", () => {
        this.__reloadCurrentModel();
      }, this);
    },

    _addItemsToLayout: function() {
      this.__addInputNodesLayout();
      this._addWorkbenchLayer();
      this.__addExtras();
      this.__addOutputNodesLayout();
    },

    __addInputNodesLayout: function() {
      const inputNodesLayout = this.__inputNodesLayout = this.__createInputOutputNodesLayout(true);
      this._add(inputNodesLayout);
    },

    _addWorkbenchLayer: function() {
      const workbenchLayer = this.__workbenchLayer = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      this._add(workbenchLayer, {
        flex: 1
      });

      const workbenchLayoutScroll = this._workbenchLayoutScroll = new qx.ui.container.Scroll();
      osparc.utils.Utils.setIdToWidget(workbenchLayoutScroll, "WorkbenchUI-scroll");
      const workbenchLayout = this.__workbenchLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      workbenchLayoutScroll.add(workbenchLayout);
      workbenchLayer.add(workbenchLayoutScroll, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });

      this.__addDesktop();
      this.__addSVGLayer();
    },

    __addDesktop: function() {
      const desktop = this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
      this.__workbenchLayout.add(desktop, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });
    },

    __addSVGLayer: function() {
      const svgLayer = this.__svgLayer = new osparc.component.workbench.SvgWidget();
      this.__desktop.add(svgLayer, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });
    },

    __addExtras: function() {
      this.__addStartHint();
      this.__addZoomToolbar();
      this.__addUnlinkButton();
    },

    __addOutputNodesLayout: function() {
      const nodesExposedLayout = this.__outputNodesLayout = this.__createInputOutputNodesLayout(false);
      this._add(nodesExposedLayout);
    },

    __addStartHint: function() {
      this.__startHint = new qx.ui.basic.Label(this.tr("Double click to start adding a node")).set({
        font: "workbench-start-hint",
        textColor: "workbench-start-hint",
        visibility: "excluded"
      });
      this.__workbenchLayout.add(this.__startHint);
    },

    __addZoomToolbar: function() {
      const zoomToolbar = new qx.ui.toolbar.ToolBar().set({
        spacing: 0,
        opacity: 0.8
      });
      zoomToolbar.add(this.__getZoomOutButton());
      zoomToolbar.add(this.__getZoomResetButton());
      zoomToolbar.add(this.__getZoomInButton());

      this.__workbenchLayer.add(zoomToolbar, {
        left: 10,
        bottom: 10
      });
    },

    __addUnlinkButton: function() {
      const unlinkButton = this.__unlinkButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/unlink/18",
        width: BUTTON_SIZE,
        height: BUTTON_SIZE,
        visibility: "excluded"
      });
      unlinkButton.addListener("execute", () => {
        if (this.__selectedItemId && this.__isSelectedItemAnEdge()) {
          this.__removeEdge(this.__getEdgeUI(this.__selectedItemId));
          this.__selectedItemChanged(null);
        }
      }, this);

      this.__workbenchLayer.add(unlinkButton, {
        bottom: 10,
        right: 10
      });
    },

    __getWorkbench: function() {
      return this.getStudy().getWorkbench();
    },

    __getZoomBtn: function(icon, tooltip) {
      const btn = new qx.ui.toolbar.Button(null, icon+"/18").set({
        width: ZOOM_BUTTON_SIZE,
        height: ZOOM_BUTTON_SIZE
      });
      if (tooltip) {
        btn.setToolTipText(tooltip);
      }
      return btn;
    },

    __getZoomInButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/zoom_in", this.tr("Zoom In"));
      btn.addListener("execute", () => {
        this.__zoom(true);
      }, this);
      return btn;
    },

    __getZoomOutButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/zoom_out", this.tr("Zoom Out"));
      btn.addListener("execute", () => {
        this.__zoom(false);
      }, this);
      return btn;
    },

    __getZoomResetButton: function() {
      const btn = this.__getZoomBtn("@MaterialIcons/find_replace", this.tr("Reset Zoom"));
      btn.addListener("execute", () => {
        this.setScale(1);
      }, this);
      return btn;
    },

    __createInputOutputNodesLayout: function(isInput) {
      const label = isInput ? this.tr("INPUTS") : this.tr("OUTPUTS");
      const inputOutputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      inputOutputNodesLayout.set({
        width: NODE_INPUTS_WIDTH,
        maxWidth: NODE_INPUTS_WIDTH,
        allowGrowX: false,
        padding: [0, 6]
      });
      inputOutputNodesLayout.getContentElement().setStyles(this.self().getDashedBorderSytle(isInput));
      const title = new qx.ui.basic.Label(label).set({
        alignX: "center",
        margin: [15, 0],
        font: "workbench-io-label",
        textColor: "workbench-start-hint"
      });
      inputOutputNodesLayout.add(title);

      return inputOutputNodesLayout;
    },

    __openServiceCatalog: function(e) {
      if (this.getStudy().isReadOnly()) {
        return;
      }
      const winPos = this.__pointerEventToScreenPos(e);
      const nodePos = this.__pointerEventToWorkbenchPos(e);
      this.openServiceCatalog(winPos, nodePos);
    },

    openServiceCatalog: function(winPos, nodePos) {
      const srvCat = new osparc.component.workbench.ServiceCatalog();
      const maxLeft = this.getBounds().width - osparc.component.workbench.ServiceCatalog.Width;
      const maxHeight = this.getBounds().height - osparc.component.workbench.ServiceCatalog.Height;
      const posX = Math.min(winPos.x, maxLeft);
      const posY = Math.min(winPos.y, maxHeight);
      srvCat.moveTo(posX + this.__getLeftOffset(), posY + this.__getTopOffset());
      srvCat.addListener("addService", e => {
        const {
          service,
          nodeLeftId,
          nodeRightId
        } = e.getData();
        const newNodeUI = this.__addNode(service, nodePos);
        if (nodeLeftId !== null || nodeRightId !== null) {
          const newNodeId = newNodeUI.getNodeId();
          this._createEdgeBetweenNodes({
            nodeId: nodeLeftId ? nodeLeftId : newNodeId
          }, {
            nodeId: nodeRightId ? nodeRightId : newNodeId
          });
        }
      }, this);
      srvCat.open();
      return srvCat;
    },

    __addNode: function(service, pos) {
      let parent = null;
      if (this._currentModel.isContainer()) {
        parent = this._currentModel;
      }
      const node = this.__getWorkbench().createNode(service.getKey(), service.getVersion(), null, parent);
      if (!node) {
        return null;
      }

      const newNodeUI = this._createNodeUI(node.getNodeId());
      this.__createDragDropMechanism(newNodeUI);
      this._addNodeUIToWorkbench(newNodeUI, pos);
      return newNodeUI;
    },

    __getNodesBounds: function() {
      if (this.__nodesUI.length === 0) {
        return null;
      }

      const bounds = {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      };
      this.__nodesUI.forEach(nodeUI => {
        const nodeBounds = nodeUI.getBounds();
        /*
        // nodeBounds postion might be wrong
        bounds.left = Math.max(bounds.left, nodeBounds.left);
        bounds.top = Math.max(bounds.top, nodeBounds.top);
        bounds.right = Math.max(bounds.right, nodeBounds.left + nodeBounds.width);
        bounds.bottom = Math.max(bounds.bottom, nodeBounds.top + nodeBounds.height);
        */
        const nodePos = nodeUI.getNode().getPosition();
        bounds.left = Math.max(bounds.left, nodePos.x);
        bounds.top = Math.max(bounds.top, nodePos.y);
        bounds.right = Math.max(bounds.right, nodePos.x + nodeBounds.width);
        bounds.bottom = Math.max(bounds.bottom, nodePos.y + nodeBounds.height);
      });
      return bounds;
    },

    _addNodeUIToWorkbench: function(nodeUI, position) {
      if (position === undefined || !("x" in position) || isNaN(position["x"]) || position["x"] < 0) {
        position = {
          x: 10,
          y: 10
        };
      }

      const node = nodeUI.getNode();
      node.setPosition(position);
      nodeUI.moveTo(node.getPosition().x, node.getPosition().y);
      this.__desktop.add(nodeUI);
      nodeUI.open();
      this.__nodesUI.push(nodeUI);

      nodeUI.addListener("appear", () => {
        this.__updateNodeUIPos(nodeUI);
      }, this);

      const isStudyReadOnly = this.getStudy().isReadOnly();
      nodeUI.set({
        movable: !isStudyReadOnly,
        selectable: !isStudyReadOnly,
        focusable: !isStudyReadOnly
      });
      if (isStudyReadOnly) {
        nodeUI.getChildControl("captionbar").set({
          cursor: "default"
        });
      } else {
        this.__addNodeListeners(nodeUI);
      }

      qx.ui.core.queue.Layout.flush();

      this.__updateHint();
    },

    __addNodeListeners: function(nodeUI) {
      nodeUI.addListener("nodeStartedMoving", () => {
        this.getSelectedNodes().forEach(selectedNodeUI => {
          selectedNodeUI.initPos = selectedNodeUI.getNode().getPosition();
        });
      }, this);

      nodeUI.addListener("nodeMoving", () => {
        this.__updateNodeUIPos(nodeUI);
        if ("initPos" in nodeUI) {
          const xDiff = nodeUI.getNode().getPosition().x - nodeUI.initPos.x;
          const yDiff = nodeUI.getNode().getPosition().y - nodeUI.initPos.y;
          this.getSelectedNodes().forEach(selectedNodeUI => {
            if (nodeUI.getNodeId() !== selectedNodeUI.getNodeId()) {
              const selectedNode = selectedNodeUI.getNode();
              selectedNode.setPosition({
                x: selectedNodeUI.initPos.x + xDiff,
                y: selectedNodeUI.initPos.y + yDiff
              });
              selectedNodeUI.moveTo(selectedNode.getPosition().x, selectedNode.getPosition().y);
              this.__updateNodeUIPos(selectedNodeUI);
            }
          });
        }
      }, this);

      nodeUI.addListener("nodeStoppedMoving", () => {
        this.getSelectedNodes().forEach(selectedNodeUI => {
          delete selectedNodeUI["initPos"];
        });

        this.__updateWorkbenchBounds();

        // After moving a nodeUI, a new element with z-index 100000+ appears on the DOM tree and prevents from clicking
        // elsewhere. Here we go through every the children of the WorkbenchUI and remove the undesired element
        const allChildren = Array.from(this.getContentElement().getDomElement().getElementsByTagName("*"));
        const nodesAndSuspicious = allChildren.filter(child => parseInt(child.style.zIndex) >= 100000);
        nodesAndSuspicious.forEach(child => {
          if (child.className !== "qx-window-small-cap") {
            console.warn("moving undesired element to background");
            child.style.zIndex = "1";
          }
        });
      }, this);

      nodeUI.addListener("tap", e => {
        this.activeNodeChanged(nodeUI, e.isCtrlPressed());
        e.stopPropagation();
      }, this);

      nodeUI.addListener("dbltap", e => {
        this.fireDataEvent("nodeSelected", nodeUI.getNodeId());
        e.stopPropagation();
      }, this);
    },

    getCurrentModel: function() {
      return this._currentModel;
    },

    getSelectedNodes: function() {
      return this.__selectedNodes;
    },

    getSelectedNodeIDs: function() {
      const selectedNodeIDs = [];
      this.__selectedNodes.forEach(nodeUI => {
        selectedNodeIDs.push(nodeUI.getNodeId());
      });
      return selectedNodeIDs;
    },

    resetSelectedNodes: function() {
      this.__selectedNodes.forEach(node => node.removeState("selected"));
      this.__selectedNodes = [];
      qx.event.message.Bus.dispatchByName("changeWorkbenchSelection", []);
    },

    activeNodeChanged: function(activeNode, isControlPressed = false) {
      if (isControlPressed) {
        if (this.__selectedNodes.includes(activeNode)) {
          const index = this.__selectedNodes.indexOf(activeNode);
          this.__selectedNodes.splice(index, 1);
          activeNode.removeState("selected");
        } else {
          this.__selectedNodes.push(activeNode);
          activeNode.addState("selected");
        }
      } else {
        this.__selectedNodes.forEach(node => node.removeState("selected"));
        this.__selectedNodes = [activeNode];
        activeNode.addState("selected");
      }
      this.__selectedItemChanged(activeNode.getNodeId());
      qx.event.message.Bus.dispatchByName("changeWorkbenchSelection", this.__selectedNodes.map(selected => selected.getNode()));
    },

    _createNodeUI: function(nodeId) {
      const node = this.__getWorkbench().getNode(nodeId);

      const nodeUI = new osparc.component.workbench.NodeUI(node);
      this.bind("scale", nodeUI, "scale");
      nodeUI.populateNodeLayout();
      nodeUI.addListener("renameNode", e => this.__openNodeRenamer(e.getData()), this);
      nodeUI.addListener("infoNode", e => this.__openNodeInfo(e.getData()), this);
      nodeUI.addListener("removeNode", e => this.fireDataEvent("removeNode", e.getData()), this);

      return nodeUI;
    },

    __createEdgeUI: function(node1Id, node2Id, edgeId) {
      const edge = this.__getWorkbench().createEdge(edgeId, node1Id, node2Id);
      if (!edge) {
        return null;
      }
      if (this.__edgeRepresetationExists(edge)) {
        return null;
      }

      // build representation
      const nodeUI1 = this.getNodeUI(node1Id);
      const nodeUI2 = this.getNodeUI(node2Id);
      if (nodeUI1.getCurrentBounds() === null || nodeUI2.getCurrentBounds() === null) {
        console.error("bounds not ready");
        return null;
      }
      const port1 = nodeUI1.getOutputPort();
      const port2 = nodeUI2.getInputPort();
      if (port1 && port2) {
        if (this._currentModel.isContainer() && nodeUI2.getNodeId() === this._currentModel.getNodeId()) {
          this._currentModel.addOutputNode(nodeUI1.getNodeId());
        } else {
          nodeUI2.getNode().addInputNode(node1Id);
        }
        const pointList = this.__getEdgePoints(nodeUI1, port1, nodeUI2, port2);
        const x1 = pointList[0] ? pointList[0][0] : 0;
        const y1 = pointList[0] ? pointList[0][1] : 0;
        const x2 = pointList[1] ? pointList[1][0] : 0;
        const y2 = pointList[1] ? pointList[1][1] : 0;
        const edgeRepresentation = this.__svgLayer.drawCurve(x1, y1, x2, y2, !edge.isPortConnected());

        edge.addListener("changePortConnected", e => {
          const portConnected = e.getData();
          osparc.component.workbench.SvgWidget.updateCurveDashes(edgeRepresentation, !portConnected);
        }, this);

        const edgeUI = new osparc.component.workbench.EdgeUI(edge, edgeRepresentation);
        this.__edgesUI.push(edgeUI);

        const that = this;
        edgeUI.getRepresentation().node.addEventListener("click", e => {
          // this is needed to get out of the context of svg
          that.__selectedItemChanged(edgeUI.getEdgeId()); // eslint-disable-line no-underscore-dangle
          e.stopPropagation();
        }, this);

        return edgeUI;
      }
      return null;
    },

    __edgeRepresetationExists: function(edge) {
      for (let i=0; i<this.__edgesUI.length; i++) {
        const edgeUI = this.__edgesUI[i];
        if (edgeUI.getEdge().getEdgeId() === edge.getEdgeId()) {
          return true;
        }
      }
      return false;
    },

    __createDragDropMechanism: function(nodeUI) {
      if (this.getStudy().isReadOnly()) {
        return;
      }

      const evType = "pointermove";
      nodeUI.addListener("edgeDragStart", e => {
        let data = e.getData();
        let event = data.event;
        let dragNodeId = data.nodeId;
        let dragIsInput = data.isInput;

        // Register supported actions
        event.addAction("move");

        // Register supported types
        event.addType("osparc-node-link");
        let dragData = {
          dragNodeId: dragNodeId,
          dragIsInput: dragIsInput
        };
        event.addData("osparc-node-link", dragData);

        this.__tempEdgeNodeId = dragData.dragNodeId;
        this.__tempEdgeIsInput = dragData.dragIsInput;

        qx.bom.Element.addListener(
          this.__desktop,
          evType,
          this.__updateTempEdge,
          this
        );
        nodeUI.setActive(false);
      }, this);

      nodeUI.addListener("edgeDragOver", e => {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        let compatible = false;
        if (event.supportsType("osparc-node-link")) {
          const dragNodeId = event.getData("osparc-node-link").dragNodeId;
          const dragIsInput = event.getData("osparc-node-link").dragIsInput;
          const dragNode = this.getNodeUI(dragNodeId);
          const dropNode = this.getNodeUI(dropNodeId);
          const dragPortTarget = dragIsInput ? dragNode.getInputPort() : dragNode.getOutputPort();
          const dropPortTarget = dropIsInput ? dropNode.getInputPort() : dropNode.getOutputPort();
          compatible = dragPortTarget.isInput !== dropPortTarget.isInput;
        }

        if (!compatible) {
          event.preventDefault();
        }
      }, this);

      nodeUI.addListener("edgeDrop", e => {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        if (event.supportsType("osparc-node-link")) {
          let dragNodeId = event.getData("osparc-node-link").dragNodeId;
          let dragIsInput = event.getData("osparc-node-link").dragIsInput;

          let nodeAId = dropIsInput ? dragNodeId : dropNodeId;
          let nodeBId = dragIsInput ? dragNodeId : dropNodeId;

          this._createEdgeBetweenNodes({
            nodeId: nodeAId
          }, {
            nodeId: nodeBId
          });
          this.__removeTempEdge();
          qx.bom.Element.removeListener(
            this.__desktop,
            evType,
            this.__updateTempEdge,
            this
          );
        }
      }, this);

      nodeUI.addListener("edgeDragEnd", e => {
        if (this.__pointerPos === null) {
          return;
        }
        let data = e.getData();
        let dragNodeId = data.nodeId;

        if (this.__tempEdgeNodeId === dragNodeId) {
          const winPos = this.__unscaleCoordinates(this.__pointerPos.x, this.__pointerPos.y);
          const srvCat = this.openServiceCatalog(winPos, this.__pointerPos);
          this.__tempEdgeIsInput === true ? srvCat.setContext(null, dragNodeId) : srvCat.setContext(dragNodeId, null);
          srvCat.addListener("close", () => this.__removeTempEdge(), this);
        }
        qx.bom.Element.removeListener(
          this.__desktop,
          evType,
          this.__updateTempEdge,
          this
        );
      }, this);
    },

    __createNodeInputUI: function(inputNode) {
      let nodeInput = new osparc.component.widget.NodeInput(inputNode);
      nodeInput.populateNodeLayout();
      this.__createDragDropMechanism(nodeInput);
      this.__inputNodesLayout.add(nodeInput, {
        flex: 1
      });
      return nodeInput;
    },

    __createNodeInputUIs: function(model) {
      this.__clearNodeInputUIs();
      const inputNodeIds = model.getInputNodes();
      inputNodeIds.forEach(inputNodeId => {
        const inputNode = this.__getWorkbench().getNode(inputNodeId);
        const inputNodeUI = this.__createNodeInputUI(inputNode);
        this.__nodesUI.push(inputNodeUI);
      });
    },

    __clearNodeInputUIs: function() {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length - 1);
      }
    },

    __createNodeOutputUI: function(currentModel) {
      let nodeOutput = new osparc.component.widget.NodeOutput(currentModel);
      nodeOutput.populateNodeLayout();
      this.__createDragDropMechanism(nodeOutput);
      this.__outputNodesLayout.add(nodeOutput, {
        flex: 1
      });
      return nodeOutput;
    },

    __createNodeOutputUIs: function(model) {
      this.__clearNodeOutputUIs();
      let outputNodeUI = this.__createNodeOutputUI(model);
      this.__nodesUI.push(outputNodeUI);
    },

    __clearNodeOutputUIs: function() {
      // remove all but the title
      while (this.__outputNodesLayout.getChildren().length > 1) {
        this.__outputNodesLayout.removeAt(this.__outputNodesLayout.getChildren().length - 1);
      }
    },

    _createEdgeBetweenNodes: function(from, to, edgeId) {
      const node1Id = from.nodeId;
      const node2Id = to.nodeId;
      this.__createEdgeUI(node1Id, node2Id, edgeId);
    },

    _createEdgeBetweenNodesAndInputNodes: function(from, to, edgeId) {
      const inputNodes = this.__inputNodesLayout.getChildren();
      // Children[0] is the title
      for (let i = 1; i < inputNodes.length; i++) {
        const inputNodeId = inputNodes[i].getNodeId();
        if (inputNodeId === from.nodeId) {
          let node1Id = from.nodeId;
          let node2Id = to.nodeId;
          this.__createEdgeUI(node1Id, node2Id, edgeId);
        }
      }
    },

    __updateAllEdges: function() {
      this.__nodesUI.forEach(nodeUI => {
        this.__updateNodeUIPos(nodeUI);
      });
    },

    __updateEdges: function(nodeUI) {
      let edgesInvolved = [];
      if (nodeUI.getNodeType() === "service") {
        edgesInvolved = this.__getWorkbench().getConnectedEdges(nodeUI.getNodeId());
      }

      edgesInvolved.forEach(edgeId => {
        let edgeUI = this.__getEdgeUI(edgeId);
        if (edgeUI) {
          let node1 = null;
          if (edgeUI.getEdge().getInputNodeId()) {
            node1 = this.getNodeUI(edgeUI.getEdge().getInputNodeId());
          }
          let port1 = node1.getOutputPort();
          let node2 = this.getNodeUI(edgeUI.getEdge().getOutputNodeId());
          let port2 = node2.getInputPort();
          const pointList = this.__getEdgePoints(node1, port1, node2, port2);
          const x1 = pointList[0][0];
          const y1 = pointList[0][1];
          const x2 = pointList[1][0];
          const y2 = pointList[1][1];
          osparc.component.workbench.SvgWidget.updateCurve(edgeUI.getRepresentation(), x1, y1, x2, y2);
        }
      });
    },

    __updateNodeUIPos: function(nodeUI) {
      this.__updateEdges(nodeUI);

      this.__updateWorkbenchBounds();
    },

    __getLeftOffset: function() {
      const leftOffset = window.innerWidth - this.getInnerSize().width;
      return leftOffset;
    },

    __getTopOffset: function() {
      const topOffset = window.innerHeight - this.getInnerSize().height;
      return topOffset;
    },

    __pointerEventToScreenPos: function(e) {
      const leftOffset = this.__getLeftOffset();
      const inputNodesLayoutWidth = this.__inputNodesLayout && this.__inputNodesLayout.isVisible() ? this.__inputNodesLayout.getWidth() : 0;
      return {
        x: e.getDocumentLeft() - leftOffset - inputNodesLayoutWidth,
        y: e.getDocumentTop() - this.__getTopOffset()
      };
    },

    __screenToToWorkbenchPos: function(x, y) {
      const scaledPos = this.__scaleCoordinates(x, y);
      const scrollX = this._workbenchLayoutScroll.getScrollX();
      const scrollY = this._workbenchLayoutScroll.getScrollY();
      const scaledScroll = this.__scaleCoordinates(scrollX, scrollY);
      return {
        x: scaledPos.x + scaledScroll.x,
        y: scaledPos.y + scaledScroll.y
      };
    },

    __pointerEventToWorkbenchPos: function(e) {
      const {
        x,
        y
      } = this.__pointerEventToScreenPos(e);
      return this.__screenToToWorkbenchPos(x, y);
    },

    __updateTempEdge: function(e) {
      let nodeUI = null;
      if (this.__tempEdgeNodeId !== null) {
        nodeUI = this.getNodeUI(this.__tempEdgeNodeId);
      }
      if (nodeUI === null) {
        return;
      }
      let port;
      if (this.__tempEdgeIsInput) {
        port = nodeUI.getInputPort();
      } else {
        port = nodeUI.getOutputPort();
      }
      if (port === null) {
        return;
      }

      const scaledPos = this.__pointerEventToWorkbenchPos(e);
      this.__pointerPos = {
        x: scaledPos.x,
        y: scaledPos.y
      };

      let portPos = nodeUI.getEdgePoint(port);
      if (portPos[0] === null) {
        portPos[0] = parseInt(this.__workbenchLayout.getBounds().width - 6);
      }

      let x1;
      let y1;
      let x2;
      let y2;
      if (port.isInput) {
        x1 = this.__pointerPos.x;
        y1 = this.__pointerPos.y;
        x2 = portPos[0];
        y2 = portPos[1];
      } else {
        x1 = portPos[0];
        y1 = portPos[1];
        x2 = this.__pointerPos.x;
        y2 = this.__pointerPos.y;
      }

      if (this.__tempEdgeRepr === null) {
        this.__tempEdgeRepr = this.__svgLayer.drawCurve(x1, y1, x2, y2, true);
      } else {
        osparc.component.workbench.SvgWidget.updateCurve(this.__tempEdgeRepr, x1, y1, x2, y2);
      }
      const portLabel = port.isInput ? nodeUI.getInputPort() : nodeUI.getOutputPort();
      portLabel.setSource(osparc.component.workbench.BaseNodeUI.NODE_CONNECTED);

      if (!this.__tempEdgeIsInput) {
        const modified = nodeUI.getNode().getStatus().getModified();
        const colorHex = osparc.component.workbench.EdgeUI.getEdgeColor(modified);
        osparc.component.workbench.SvgWidget.updateCurveColor(this.__tempEdgeRepr, colorHex);
      }
    },

    __removeTempEdge: function() {
      if (this.__tempEdgeRepr !== null) {
        osparc.component.workbench.SvgWidget.removeCurve(this.__tempEdgeRepr);
      }

      const nodeUI = this.getNodeUI(this.__tempEdgeNodeId);
      if (nodeUI) {
        const isConnected = this.__tempEdgeIsInput ? nodeUI.getNode().getInputConnected() : nodeUI.getNode().getOutputConnected();
        const portLabel = this.__tempEdgeIsInput ? nodeUI.getInputPort() : nodeUI.getOutputPort();
        portLabel.set({
          source: isConnected ? osparc.component.workbench.BaseNodeUI.NODE_CONNECTED : osparc.component.workbench.BaseNodeUI.NODE_DISCONNECTED
        });
      }

      this.__tempEdgeRepr = null;
      this.__tempEdgeNodeId = null;
      this.__tempEdgeIsInput = null;
      this.__pointerPos = null;
    },

    __getEdgePoints: function(node1, port1, node2, port2) {
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }
      let p1 = node1.getEdgePoint(port1);
      let p2 = node2.getEdgePoint(port2);
      if (p2[0] === null) {
        p2[0] = parseInt(this.__workbenchLayout.getBounds().width - 6);
      }
      return [p1, p2];
    },

    getNodeUI: function(nodeId) {
      return this.__nodesUI.find(nodeUI => nodeUI.getNodeType() === "service" && nodeUI.getNodeId() === nodeId);
    },

    __getEdgeUI: function(edgeId) {
      for (let i = 0; i < this.__edgesUI.length; i++) {
        if (this.__edgesUI[i].getEdgeId() === edgeId) {
          return this.__edgesUI[i];
        }
      }
      return null;
    },

    clearNode(nodeId) {
      const nodeUI = this.getNodeUI(nodeId);
      this.__clearNodeUI(nodeUI);
    },

    clearEdge: function(edgeId) {
      this.__clearEdge(this.__getEdgeUI(edgeId));
    },

    __removeEdge: function(edge) {
      this.fireDataEvent("removeEdge", edge.getEdgeId());
    },

    __clearNodeUI: function(nodeUI) {
      if (this.__desktop.getChildren().includes(nodeUI)) {
        this.__desktop.remove(nodeUI);
      }
      let index = this.__nodesUI.indexOf(nodeUI);
      if (index > -1) {
        this.__nodesUI.splice(index, 1);
      }
      this.__updateHint();
    },

    __clearAllNodes: function() {
      while (this.__nodesUI.length) {
        this.__clearNodeUI(this.__nodesUI[this.__nodesUI.length-1]);
      }
    },

    __clearEdge: function(edge) {
      if (edge) {
        osparc.component.workbench.SvgWidget.removeCurve(edge.getRepresentation());
        const index = this.__edgesUI.indexOf(edge);
        if (index > -1) {
          this.__edgesUI.splice(index, 1);
        }
      }
    },

    __clearAllEdges: function() {
      while (this.__edgesUI.length > 0) {
        this.__clearEdge(this.__edgesUI[this.__edgesUI.length - 1]);
      }
    },

    _clearAll: function() {
      this.__clearAllNodes();
      this.__clearAllEdges();
    },

    loadModel: function(model) {
      if (this.__svgLayer.getReady()) {
        this._loadModel(model);
      } else {
        this.__svgLayer.addListenerOnce("SvgWidgetReady", () => {
          this._loadModel(model);
        }, this);
      }
    },

    __reloadCurrentModel: function() {
      if (this._currentModel) {
        this.loadModel(this._currentModel);
      }
    },

    _loadModel: async function(model) {
      this._clearAll();
      this.resetSelectedNodes();
      this._currentModel = model;
      if (model) {
        const isContainer = model.isContainer();
        if (isContainer) {
          this.__inputNodesLayout.setVisibility("visible");
          this.__createNodeInputUIs(model);
          this.__outputNodesLayout.setVisibility("visible");
          this.__createNodeOutputUIs(model);
        } else {
          this.__inputNodesLayout.setVisibility("excluded");
          this.__outputNodesLayout.setVisibility("excluded");
        }
        qx.ui.core.queue.Visibility.flush();

        // create nodes
        let nodes = isContainer ? model.getInnerNodes() : model.getNodes();
        const nodeUIs = [];
        for (const nodeId in nodes) {
          const node = nodes[nodeId];
          const nodeUI = this._createNodeUI(nodeId);
          this.__createDragDropMechanism(nodeUI);
          this._addNodeUIToWorkbench(nodeUI, node.getPosition());
          nodeUIs.push(nodeUI);
        }

        const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
        const allNodesVisible = nodeUIss => nodeUIss.every(nodeUI => nodeUI.getCurrentBounds() !== null);

        let tries = 0;
        while (!allNodesVisible(nodeUIs) && tries < 10) {
          await sleep(50);
          tries++;
        }

        // create edges
        for (const nodeId in nodes) {
          const node = nodes[nodeId];
          const inputNodeIDs = node.getInputNodes();
          inputNodeIDs.forEach(inputNodeId => {
            if (inputNodeId in nodes) {
              this._createEdgeBetweenNodes({
                nodeId: inputNodeId
              }, {
                nodeId: nodeId
              });
            } else {
              this._createEdgeBetweenNodesAndInputNodes({
                nodeId: inputNodeId
              }, {
                nodeId: nodeId
              });
            }
          });
        }

        if (isContainer) {
          const exposedNodeIDs = model.getExposedNodeIDs();
          exposedNodeIDs.forEach(exposedNodeID => {
            this._createEdgeBetweenNodes({
              nodeId: exposedNodeID
            }, {
              nodeId: model.getNodeId()
            });
          });
        }
      }
    },

    __selectedItemChanged: function(newID) {
      const oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemAnEdge()) {
          const edge = this.__getEdgeUI(oldId);
          edge.setSelected(false);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemAnEdge()) {
        const edge = this.__getEdgeUI(newID);
        edge.setSelected(true);
      } else {
        this.fireDataEvent("changeSelectedNode", newID);
      }

      if (this.__unlinkButton) {
        this.__unlinkButton.setVisibility(this.__isSelectedItemAnEdge() ? "visible" : "excluded");
      }
    },

    __isSelectedItemAnEdge: function() {
      return Boolean(this.__getEdgeUI(this.__selectedItemId));
    },

    __scaleCoordinates: function(x, y) {
      return {
        x: parseInt(x / this.getScale()),
        y: parseInt(y / this.getScale())
      };
    },

    __unscaleCoordinates: function(x, y) {
      return {
        x: parseInt(x * this.getScale()),
        y: parseInt(y * this.getScale())
      };
    },

    __openContextMenu: function(e) {
      const radialMenuWrapper = osparc.wrapper.RadialMenu.getInstance();
      if (radialMenuWrapper.getLibReady()) {
        this.__doOpenContextMenu(e);
      } else {
        radialMenuWrapper.init()
          .then(loaded => {
            if (loaded) {
              this.__doOpenContextMenu(e);
            }
          });
      }
    },

    __doOpenContextMenu: function(e) {
      if (this.__contextMenu) {
        this.__contextMenu.hide();
      }
      const buttons = [{
        "text": "\uf067", // plus
        "action": () => {
          this.__openServiceCatalog(e);
        }
      }, {
        "text": "\uf00e", // search-plus
        "action": () => {
          this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
          this.__zoom(true);
        }
      }, {
        "text": "\uf002", // search
        "action": () => {
          this.setScale(1);
        }
      }, {
        "text": "\uf010", // search-minus
        "action": () => {
          this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
          this.__zoom(false);
        }
      }];
      let rotation = 3 * Math.PI / 2;
      rotation -= (2/buttons.length) * (Math.PI / 2);
      const radialMenuWrapper = osparc.wrapper.RadialMenu.getInstance();
      const contextMenu = this.__contextMenu = radialMenuWrapper.createMenu({rotation});
      contextMenu.addButtons(buttons);
      contextMenu.setPos(e.getDocumentLeft() - contextMenu.w2, e.getDocumentTop() - contextMenu.h2);
      contextMenu.show();
    },

    __mouseDown: function(e) {
      if (e.isRightPressed()) {
        this.__openContextMenu(e);
      } else if (e.isMiddlePressed()) {
        this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
        this.__panning = true;
        this.set({
          cursor: "move"
        });
      }
    },

    __mouseMove: function(e) {
      if (this.__panning && e.isMiddlePressed()) {
        const oldPos = this.__pointerPos;
        const newPos = this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
        const moveX = parseInt((oldPos.x-newPos.x) * this.getScale());
        const moveY = parseInt((oldPos.y-newPos.y) * this.getScale());
        this._workbenchLayoutScroll.scrollToX(this._workbenchLayoutScroll.getScrollX() + moveX);
        this._workbenchLayoutScroll.scrollToY(this._workbenchLayoutScroll.getScrollY() + moveY);
        this.set({
          cursor: "move"
        });
      } else if (this.__isDraggingLink) {
        this.__draggingLink(e, true);
      }
    },

    __mouseUp: function(e) {
      if (this.__panning) {
        this.__panning = false;
        this.set({
          cursor: "auto"
        });
      } else if (this.__isDraggingLink) {
        this.__dropLink(e);
      }
    },

    __mouseWheel: function(e) {
      this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
      const zoomIn = e.getWheelDelta() < 0;
      this.__zoom(zoomIn);
    },

    __zoom: function(zoomIn = true) {
      const zoomValues = this.self().ZOOM_VALUES;
      const nextItem = () => {
        const i = zoomValues.indexOf(this.getScale());
        if (i+1<zoomValues.length) {
          return zoomValues[i+1];
        }
        return zoomValues[i];
      };
      const prevItem = () => {
        const i = zoomValues.indexOf(this.getScale());
        if (i-1>=0) {
          return zoomValues[i-1];
        }
        return zoomValues[i];
      };

      const newScale = zoomIn ? nextItem() : prevItem();
      this.setScale(newScale);
    },

    __zoomAll: function() {
      const zoomValues = this.self().ZOOM_VALUES;
      const nodeBounds = this.__getNodesBounds();
      if (nodeBounds === null) {
        return;
      }
      const screenWidth = this.getBounds().width - 10; // scrollbar
      const screenHeight = this.getBounds().height - 10; // scrollbar
      if (nodeBounds.right < screenWidth && nodeBounds.bottom < screenHeight) {
        return;
      }

      const minScale = Math.min(screenWidth/nodeBounds.right, screenHeight/nodeBounds.bottom);
      const posibleZooms = zoomValues.filter(zoomValue => zoomValue < minScale);
      const zoom = Math.max(...posibleZooms);
      if (zoom) {
        this.setScale(zoom);
      }
    },

    __applyScale: function(value) {
      const el = this.__workbenchLayout.getContentElement().getDomElement();
      osparc.utils.Utils.setZoom(el, value);

      this.__updateWorkbenchBounds();
    },

    __updateWorkbenchBounds: function() {
      const nodeBounds = this.__getNodesBounds();
      if (nodeBounds === null) {
        this.__updateHint();
        return;
      }

      // Fit to nodes size
      let scale = this.getScale();
      const nodesWidth = nodeBounds.right + osparc.component.workbench.NodeUI.NODE_WIDTH;
      const nodesHeight = nodeBounds.bottom + osparc.component.workbench.NodeUI.NODE_HEIGHT;
      const scaledWidth = parseInt(nodesWidth * scale);
      const scaledHeight = parseInt(nodesHeight * scale);
      let wbWidth = scaledWidth;
      let wbHeight = scaledHeight;
      this.__workbenchLayout.set({
        minWidth: scale > 1 ? scaledWidth : nodesWidth,
        minHeight: scale > 1 ? scaledHeight : nodesHeight
      });
      this.__workbenchLayout.set({
        width: scale > 1 ? scaledWidth : nodesWidth,
        height: scale > 1 ? scaledHeight : nodesHeight
      });

      // Fill Screen
      const screenWidth = this.getBounds().width - 10; // scrollbar
      const screenHeight = this.getBounds().height - 10; // scrollbar
      const scaledScreenWidth = parseInt(screenWidth / scale);
      const scaledScreenHeight = parseInt(screenHeight / scale);
      if (this.__workbenchLayout.getWidth() < scaledScreenWidth) {
        wbWidth = 0;
        this.__workbenchLayout.set({
          minWidth: scaledScreenWidth
        });
      }
      if (this.__workbenchLayout.getHeight() < scaledScreenHeight) {
        wbHeight = 0;
        this.__workbenchLayout.set({
          minHeight: scaledScreenHeight
        });
      }

      // Hack/Workaround: recalculate sliders
      setTimeout(() => {
        // eslint-disable-next-line no-underscore-dangle
        this._workbenchLayoutScroll._computeScrollbars();

        const paneSize = this._workbenchLayoutScroll.getChildControl("pane").getInnerSize();
        const barX = this._workbenchLayoutScroll.getChildControl("scrollbar-x");
        const barY = this._workbenchLayoutScroll.getChildControl("scrollbar-y");
        const sliderKnobX = barX.getChildControl("slider").getChildControl("knob");
        const sliderKnobY = barY.getChildControl("slider").getChildControl("knob");
        if (wbWidth > paneSize.width) {
          barX.setMaximum(wbWidth - paneSize.width);
          barX.setKnobFactor(paneSize.width / wbWidth);
          sliderKnobX.resetBackgroundColor();
        } else {
          barX.setMaximum(0);
          barX.setKnobFactor(1);
          // changing visibility triggers _computeScrollbars, which undoes the workaround
          sliderKnobX.setBackgroundColor("transparent");
        }
        if (wbHeight > paneSize.height) {
          barY.setMaximum(wbHeight - paneSize.height);
          barY.setKnobFactor(paneSize.height / wbHeight);
          sliderKnobY.resetBackgroundColor();
        } else {
          barY.setMaximum(0);
          barY.setKnobFactor(1);
          // changing visibility triggers _computeScrollbars, which undoes the workaround
          sliderKnobY.setBackgroundColor("transparent");
        }
      }, 20);
    },

    __fillScreen: function() {
      const scale = this.getScale();
      const screenWidth = this.getBounds().width - 10; // scrollbar
      const screenHeight = this.getBounds().height - 10; // scrollbar
      const scaledScreenWidth = parseInt(screenWidth/scale);
      const scaledScreenHeight = parseInt(screenHeight/scale);
      if (this.__workbenchLayout.getWidth() < scaledScreenWidth) {
        console.log("Fill width");
        this.__workbenchLayout.set({
          width: scaledScreenWidth
        });
      }
      if (this.__workbenchLayout.getHeight() < scaledScreenHeight) {
        console.log("Fill height");
        this.__workbenchLayout.set({
          height: scaledScreenHeight
        });
      }
    },

    __openNodeRenamer: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      const treeItemRenamer = new osparc.component.widget.Renamer(node.getLabel());
      treeItemRenamer.addListener("labelChanged", e => {
        const {
          newLabel
        } = e.getData();
        if (node) {
          node.renameNode(newLabel);
        }
        treeItemRenamer.close();
      }, this);
      treeItemRenamer.center();
      treeItemRenamer.open();
    },

    __openNodeInfo: function(nodeId) {
      if (nodeId) {
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        const serviceDetails = new osparc.servicecard.Large(node.getMetaData());
        const title = this.tr("Service information");
        const width = 600;
        const height = 700;
        osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
      }
    },

    _addEventListeners: function() {
      this.addListener("appear", () => {
        // Reset filters and sidebars
        // osparc.component.filter.UIFilterController.getInstance().resetGroup("workbench");
        // osparc.component.filter.UIFilterController.getInstance().setContainerVisibility("workbench", "visible");

        // qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", false);

        this.addListener("resize", () => this.__updateAllEdges(), this);
      });

      this.addListener("keypress", keyEvent => {
        const selectedNodeIDs = this.getSelectedNodeIDs();
        if (selectedNodeIDs.length === 1) {
          switch (keyEvent.getKeyIdentifier()) {
            case "F2":
              this.__openNodeRenamer(selectedNodeIDs[0]);
              break;
            case "I":
              this.__openNodeInfo(selectedNodeIDs[0]);
              break;
            case "Delete":
              this.fireDataEvent("removeNode", selectedNodeIDs[0]);
              break;
            case "Escape":
              this.resetSelectedNodes();
              break;
          }
        }
      }, this);

      this.addListenerOnce("appear", () => {
        const domEl = this.getContentElement().getDomElement();
        [
          "dragenter",
          "dragover",
          "dragleave"
        ].forEach(signalName => {
          domEl.addEventListener(signalName, e => {
            const dragging = signalName !== "dragleave";
            this.__draggingFile(e, dragging);
          }, this);
        });
        domEl.addEventListener("drop", this.__dropFile.bind(this), false);

        this.setDroppable(true);
        const stopDragging = e => {
          this.__isDraggingLink = null;
          this.__updateWidgets(false);
        };
        const startDragging = e => {
          this.addListenerOnce("dragleave", stopDragging, this);
          this.addListenerOnce("dragover", startDragging, this);
          this.__draggingLink(e, true);
        };
        this.addListenerOnce("dragover", startDragging, this);

        this.addListener("mousewheel", this.__mouseWheel, this);
        this.addListener("mousedown", this.__mouseDown, this);
        this.addListener("mousemove", this.__mouseMove, this);
        this.addListener("mouseup", this.__mouseUp, this);
      });

      this.addListener("disappear", () => {
        // Reset filters
        // osparc.component.filter.UIFilterController.getInstance().resetGroup("workbench");
        // osparc.component.filter.UIFilterController.getInstance().setContainerVisibility("workbench", "excluded");
      });

      this.__workbenchLayout.addListener("tap", () => {
        this.resetSelectedNodes();
        this.__selectedItemChanged(null);
      }, this);

      this.__workbenchLayout.addListener("dbltap", e => {
        this.__openServiceCatalog(e);
      }, this);

      this.__workbenchLayout.addListener("resize", () => this.__updateHint(), this);
    },

    __allowDragFile: function(e) {
      let allow = false;
      if (this.__isDraggingFile) {
        // item still being dragged
        allow = true;
      } else {
        // item drag from the outside world
        allow = e.target instanceof SVGElement;
        this.__isDraggingFile = allow;
      }
      return allow;
    },

    __allowDragLink: function(e) {
      let allow = false;
      if (this.__isDraggingLink) {
        // item still being dragged
        allow = true;
      } else if ("supportsType" in e) {
        // item drag from osparc's file tree
        allow = e.supportsType("osparc-file-link");
        if (allow) {
          // store "osparc-file-link" data in variable,
          // because the mousemove event doesn't contain that information
          this.__isDraggingLink = e.getData("osparc-file-link");
        }
      }
      return allow;
    },

    __draggingFile: function(e, dragging) {
      if (this.__allowDragFile(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      if (!this.isPropertyInitialized("study") || this.getStudy().isReadOnly()) {
        return;
      }

      const posX = e.offsetX + 2;
      const posY = e.offsetY + 2;
      this.__updateWidgets(dragging, posX, posY);
    },

    __draggingLink: function(e, dragging) {
      if (this.__allowDragLink(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      if (!this.isPropertyInitialized("study") || this.getStudy().isReadOnly()) {
        return;
      }

      const pos = this.__pointerEventToWorkbenchPos(e);
      this.__updateWidgets(dragging, pos.x, pos.y);
    },

    __updateWidgets: function(dragging, posX, posY) {
      const boxWidth = 120;
      const boxHeight = 60;
      if (this.__dropMe === null) {
        const dropHint = this.__dropMe = new qx.ui.basic.Label(this.tr("Drop me")).set({
          font: "workbench-start-hint",
          textColor: "workbench-start-hint"
        });
        dropHint.exclude();
        this.__workbenchLayout.add(dropHint);
        dropHint.rect = this.__svgLayer.drawDashedRect(boxWidth, boxHeight);
      }
      const dropMe = this.__dropMe;
      if (dragging) {
        dropMe.show();
        const dropMeBounds = dropMe.getBounds() || dropMe.getSizeHint();
        dropMe.setLayoutProperties({
          left: posX - parseInt(dropMeBounds.width/2) - parseInt(boxWidth/2),
          top: posY - parseInt(dropMeBounds.height/2)- parseInt(boxHeight/2)
        });
        if ("rect" in dropMe) {
          osparc.component.workbench.SvgWidget.updateRect(dropMe.rect, posX - boxWidth, posY - boxHeight);
        }
      } else {
        this.__removeDropHint();
      }
    },

    __dropFile: function(e) {
      this.__draggingFile(e, false);

      if ("dataTransfer" in e) {
        this.__isDraggingFile = false;
        const files = e.dataTransfer.files;
        if (files.length === 1) {
          const pos = {
            x: e.offsetX,
            y: e.offsetY
          };
          const fileList = e.dataTransfer.files;
          if (fileList.length) {
            const service = qx.data.marshal.Json.createModel(osparc.utils.Services.getFilePicker());
            const nodeUI = this.__addNode(service, pos);
            const filePicker = new osparc.file.FilePicker(nodeUI.getNode());
            filePicker.buildLayout();
            filePicker.uploadPendingFiles(fileList);
          }
        } else {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
      }
    },

    __dropLink: function(e) {
      this.__draggingLink(e, false);

      if (this.__isDraggingLink && "dragData" in this.__isDraggingLink) {
        const data = this.__isDraggingLink["dragData"];
        const pos = this.__pointerEventToWorkbenchPos(e, false);
        const service = qx.data.marshal.Json.createModel(osparc.utils.Services.getFilePicker());
        const nodeUI = this.__addNode(service, pos);
        const node = nodeUI.getNode();
        const filePicker = new osparc.file.FilePicker(node);
        filePicker.buildLayout();
        osparc.file.FilePicker.setOutputValueFromStore(node, data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
        this.__isDraggingLink = null;
      }
    },

    __updateHint: function() {
      if (!this.isPropertyInitialized("study") || this.__startHint === null) {
        return;
      }
      const isEmptyWorkspace = this.getStudy().isPipelineEmtpy();
      this.__startHint.setVisibility(isEmptyWorkspace ? "visible" : "excluded");
      if (isEmptyWorkspace) {
        const hintBounds = this.__startHint.getBounds() || this.__startHint.getSizeHint();
        const {
          height,
          width
        } = this.__workbenchLayout.getBounds();
        this.__startHint.setLayoutProperties({
          top: Math.round((height - hintBounds.height) / 2),
          left: Math.round((width - hintBounds.width) / 2)
        });
      }
    },

    __removeDropHint: function() {
      this.__dropMe.setVisibility("excluded");
      osparc.component.workbench.SvgWidget.removeRect(this.__dropMe.rect);
      this.__dropMe = null;
    }
  }
});
