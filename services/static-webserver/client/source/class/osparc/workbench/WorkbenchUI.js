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
 *   let workbenchUI = new osparc.workbench.WorkbenchUI();
 *   this.getRoot().add(workbenchUI);
 * </pre>
 */

const BUTTON_SIZE = 38;
const NODE_INPUTS_WIDTH = 210;

qx.Class.define("osparc.workbench.WorkbenchUI", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__nodesUI = [];
    this.__edgesUI = [];
    this.__selectedNodeUIs = [];
    this.__annotations = {};
    this.__selectedAnnotations = [];

    this._setLayout(new qx.ui.layout.HBox());

    this._addItemsToLayout();

    this._addEventListeners();
  },

  statics: {
    getDashedBorderStyle(isRight) {
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
    "removeNodes": "qx.event.type.Data",
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
      check: "osparc.workbench.WorkbenchUI.ZOOM_VALUES",
      init: 1,
      apply: "__applyScale",
      event: "changeScale",
      nullable: false
    }
  },

  members: {
    _currentModel: null,
    __deleteItemButton: null,
    __nodesUI: null,
    __edgesUI: null,
    __selectedNodeUIs: null,
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
    __toolHint: null,
    __dropHereNodeUI: null,
    __selectionRectInitPos: null,
    __selectionRectRepr: null,
    __panning: null,
    __isDraggingFile: null,
    __isDraggingLink: null,
    __annotations: null,
    __annotatingNote: null,
    __annotatingRect: null,
    __annotatingText: null,
    __annotationInitPos: null,
    __selectedAnnotations: null,
    __annotationEditor: null,
    __annotationLastColor: null,

    __applyStudy: function(study) {
      study.getWorkbench().addListener("reloadModel", () => this.__reloadCurrentModel(), this);
    },

    _addItemsToLayout: function() {
      this._addWorkbenchLayer();
      this.__addExtras();
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
      osparc.utils.Utils.setIdToWidget(desktop, "desktopWindow");
      this.__workbenchLayout.add(desktop, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });
    },

    __addSVGLayer: function() {
      const svgLayer = this.__svgLayer = new osparc.workbench.SvgWidget();
      this.__desktop.add(svgLayer, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });
    },

    __addExtras: function() {
      this.__addStartHint();
      this.__addToolHint();
      this.__addDeleteItemButton();
    },

    __addStartHint: function() {
      this.__startHint = new qx.ui.basic.Label(this.tr("Double click to start adding a node")).set({
        font: "workbench-start-hint",
        textColor: "workbench-start-hint",
        visibility: "excluded"
      });
      this.__workbenchLayout.add(this.__startHint);
    },

    __addToolHint: function() {
      const toolHint = this.__toolHint = new qx.ui.basic.Label().set({
        font: "workbench-start-hint",
        textColor: "workbench-start-hint",
        visibility: "excluded"
      });
      toolHint.bind("value", toolHint, "visibility", {
        converter: val => val ? "visible" : "excluded"
      });
      this.__workbenchLayout.add(this.__toolHint, {
        bottom: 20,
        left: 20
      });
    },

    __addDeleteItemButton: function() {
      const deleteItemButton = this.__deleteItemButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/trash/18",
        width: BUTTON_SIZE,
        height: BUTTON_SIZE,
        visibility: "excluded"
      });
      deleteItemButton.addListener("execute", () => {
        if (this.__isSelectedItemAnEdge()) {
          this.__removeEdge(this.__getEdgeUI(this.__selectedItemId));
          this.resetSelection();
        }
      }, this);

      this.__workbenchLayer.add(deleteItemButton, {
        bottom: 10,
        right: 10
      });
    },

    __getAnnotationEditorView: function() {
      if (this.__annotationEditor) {
        this.__workbenchLayer.remove(this.__annotationEditor);
      }

      const annotationEditor = this.__annotationEditor = new osparc.editor.AnnotationEditor().set({
        backgroundColor: "background-main-2",
        visibility: "excluded"
      });
      annotationEditor.addDeleteButton();

      this.__workbenchLayer.add(annotationEditor, {
        top: 10,
        right: 10
      });

      return annotationEditor;
    },

    __getWorkbench: function() {
      return this.getStudy().getWorkbench();
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
      inputOutputNodesLayout.getContentElement().setStyles(this.self().getDashedBorderStyle(isInput));
      const title = new qx.ui.basic.Label(label).set({
        alignX: "center",
        margin: [15, 0],
        font: "workbench-start-hint",
        textColor: "workbench-start-hint"
      });
      inputOutputNodesLayout.add(title);

      return inputOutputNodesLayout;
    },

    __openServiceCatalog: function(e) {
      const winPos = this.__pointerEventToScreenPos(e);
      const nodePos = this.__pointerEventToWorkbenchPos(e);
      this.openServiceCatalog(winPos, nodePos);
    },

    openServiceCatalog: function(winPos, nodePos) {
      if (this.getStudy().isReadOnly()) {
        return null;
      }
      if (this.getStudy().isPipelineRunning()) {
        osparc.FlashMessenger.getInstance().logAs(osparc.data.model.Workbench.CANT_ADD_NODE, "ERROR");
        return null;
      }
      const srvCat = new osparc.workbench.ServiceCatalog();
      const maxLeft = this.getBounds().width - osparc.workbench.ServiceCatalog.Width;
      const maxHeight = this.getBounds().height - osparc.workbench.ServiceCatalog.Height;
      const posX = Math.min(winPos.x, maxLeft);
      const posY = Math.min(winPos.y, maxHeight);
      srvCat.moveTo(posX + this.__getLeftOffset(), posY + this.__getTopOffset());
      srvCat.addListener("addService", async e => {
        const {
          service,
          nodeLeftId,
          nodeRightId
        } = e.getData();
        const nodeUI = await this.__addNode(service, nodePos);
        if (nodeUI && nodeLeftId !== null || nodeRightId !== null) {
          const newNodeId = nodeUI.getNodeId();
          this._createEdgeBetweenNodes(nodeLeftId ? nodeLeftId : newNodeId, nodeRightId ? nodeRightId : newNodeId, true);
        }
      }, this);
      srvCat.open();
      return srvCat;
    },

    __createTemporaryNodeUI: function(pos) {
      const boxWidth = osparc.workbench.NodeUI.NODE_WIDTH;
      const boxHeight = osparc.workbench.NodeUI.NODE_HEIGHT;
      const circleSize = 26;
      const temporaryNodeUI = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/"+circleSize).set({
        opacity: 0.8
      });
      temporaryNodeUI.getContentElement().addClass("rotate");
      this.__workbenchLayout.add(temporaryNodeUI);
      temporaryNodeUI.rect = this.__svgLayer.drawDashedRect(boxWidth, boxHeight);
      temporaryNodeUI.setLayoutProperties({
        left: pos.x + parseInt(boxWidth/2) - parseInt(circleSize/2),
        top: pos.y + parseInt(boxHeight/2) - parseInt(circleSize/2)
      });
      osparc.wrapper.Svg.updateItemPos(temporaryNodeUI.rect, pos.x, pos.y);

      return temporaryNodeUI;
    },

    __removeTemporaryNodeUI: function(temporaryNodeUI) {
      temporaryNodeUI.exclude();
      osparc.wrapper.Svg.removeItem(temporaryNodeUI.rect);
      this.__workbenchLayout.add(temporaryNodeUI);
      temporaryNodeUI = null;
    },

    __addNode: async function(service, pos) {
      // render temporary node
      let tempNodeUI = this.__createTemporaryNodeUI(pos);

      let nodeUI = null;
      try {
        const node = await this.__getWorkbench().createNode(service.getKey(), service.getVersion());
        nodeUI = this._createNodeUI(node.getNodeId());
        this._addNodeUIToWorkbench(nodeUI, pos);
        qx.ui.core.queue.Layout.flush();
        this.__createDragDropMechanism(nodeUI);
      } catch (err) {
        console.error(err);
      } finally {
        // remove temporary node
        this.__removeTemporaryNodeUI(tempNodeUI);
      }
      return nodeUI;
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
        const nodePos = nodeUI.getNode().getPosition();
        bounds.left = Math.max(bounds.left, nodePos.x);
        bounds.top = Math.max(bounds.top, nodePos.y);
        bounds.right = Math.max(bounds.right, nodePos.x + osparc.workbench.NodeUI.NODE_WIDTH);
        bounds.bottom = Math.max(bounds.bottom, nodePos.y + osparc.workbench.NodeUI.NODE_HEIGHT);
      });
      return bounds;
    },

    __cursorOnNodeUI: function(pos) {
      if (this.__nodesUI.length === 0) {
        return null;
      }
      let onNodeUI = null;
      this.__nodesUI.forEach(nodeUI => {
        const nBounds = nodeUI.getBounds();
        if (onNodeUI === null &&
          pos.x > nBounds.left &&
          pos.x < nBounds.left + nBounds.width &&
          pos.y > nBounds.top &&
          pos.y < nBounds.top + nBounds.height) {
          onNodeUI = nodeUI;
        }
      });
      return onNodeUI;
    },

    _addNodeUIToWorkbench: function(nodeUI, position) {
      if (position === undefined || !("x" in position) || isNaN(position["x"]) || position["x"] < 0) {
        position = {
          x: 10,
          y: 10
        };
      }

      nodeUI.setPosition(position);
      this.__desktop.add(nodeUI);
      nodeUI.open();
      this.__nodesUI.push(nodeUI);

      nodeUI.addListener("appear", () => this.__updateNodeUIPos(nodeUI), this);

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

      this.__updateHint();
    },

    __itemStartedMoving: function() {
      this.getSelectedNodeUIs().forEach(selectedNodeUI => selectedNodeUI.initPos = selectedNodeUI.getNode().getPosition());
      this.getSelectedAnnotations().forEach(selectedAnnotation => selectedAnnotation.initPos = selectedAnnotation.getPosition());
    },

    __itemMoving: function(itemId, xDiff, yDiff) {
      this.getSelectedNodeUIs().forEach(selectedNodeUI => {
        if (itemId !== selectedNodeUI.getNodeId()) {
          selectedNodeUI.setPosition({
            x: selectedNodeUI.initPos.x + xDiff,
            y: selectedNodeUI.initPos.y + yDiff
          });
          this.__updateNodeUIPos(selectedNodeUI);
        }
      });

      this.getSelectedAnnotations().forEach(selectedAnnotation => {
        const newPos = {
          x: selectedAnnotation.initPos.x + xDiff,
          y: selectedAnnotation.initPos.y + yDiff
        };
        selectedAnnotation.setPosition(newPos.x, newPos.y);
      });
    },

    __itemStoppedMoving: function(nodeUI) {
      this.getSelectedNodeUIs().forEach(selectedNodeUI => delete selectedNodeUI["initPos"]);
      this.getSelectedAnnotations().forEach(selectedAnnotation => delete selectedAnnotation["initPos"]);

      if (nodeUI && osparc.Preferences.getInstance().isSnapNodeToGrid()) {
        nodeUI.snapToGrid();
        // make sure nodeUI is moved, then update edges
        setTimeout(() => this.__updateNodeUIPos(nodeUI), 10);
      }

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
    },

    __addNodeListeners: function(nodeUI) {
      nodeUI.addListener("updateNodeDecorator", () => this.__updateNodeUIPos(nodeUI), this);

      nodeUI.addListener("nodeMovingStart", () => {
        this.__selectNode(nodeUI);
        this.__itemStartedMoving();
      }, this);

      nodeUI.addListener("nodeMoving", () => {
        this.__updateNodeUIPos(nodeUI);
        if ("initPos" in nodeUI) {
          // multi node move
          const xDiff = nodeUI.getNode().getPosition().x - nodeUI.initPos.x;
          const yDiff = nodeUI.getNode().getPosition().y - nodeUI.initPos.y;
          this.__itemMoving(nodeUI.getNodeId(), xDiff, yDiff);
        }
      }, this);
      nodeUI.addListener("nodeMovingStop", () => this.__itemStoppedMoving(nodeUI), this);

      nodeUI.addListener("tap", e => {
        this.__selectNode(nodeUI, e.isCtrlPressed());
        e.stopPropagation();
      }, this);

      nodeUI.addListener("dbltap", e => {
        this.fireDataEvent("nodeSelected", nodeUI.getNodeId());
        if (nodeUI.getNode().canNodeStart()) {
          nodeUI.getNode().requestStartNode();
        }
        e.stopPropagation();
      }, this);
    },

    __addAnnotationListeners: function(annotation) {
      annotation.addListener("annotationStartedMoving", () => {
        this.__selectAnnotation(annotation);
        this.__itemStartedMoving();
      }, this);

      annotation.addListener("annotationMoving", () => {
        if ("initPos" in annotation) {
          const reprPos = annotation.getRepresentationPosition();
          const xDiff = reprPos.x - annotation.initPos.x;
          const yDiff = reprPos.y - annotation.initPos.y;
          this.__itemMoving(annotation.getId(), xDiff, yDiff);
        }
      }, this);

      annotation.addListener("annotationStoppedMoving", () => this.__itemStoppedMoving(), this);

      annotation.addListener("annotationClicked", e => this.__selectAnnotation(annotation, e.getData()), this);
    },

    getCurrentModel: function() {
      return this._currentModel;
    },

    getSelectedAnnotations: function() {
      return this.__selectedAnnotations;
    },

    getSelectedNodeUIs: function() {
      return this.__selectedNodeUIs;
    },

    getSelectedNodes: function() {
      return this.getSelectedNodeUIs().map(selectedNodeUI => selectedNodeUI.getNode());
    },

    getSelectedNodeIDs: function() {
      return this.getSelectedNodeUIs().map(selectedNodeUI => selectedNodeUI.getNodeId());
    },

    resetSelection: function() {
      this.__setSelectedNodes([]);
      this.__setSelectedAnnotations([]);
      this.__setSelectedItem(null);
    },

    __setSelectedNodes: function(selectedNodeUIs) {
      this.getSelectedNodeUIs().forEach(node => {
        if (!selectedNodeUIs.includes(node)) {
          node.removeState("selected");
        }
      });
      selectedNodeUIs.forEach(selectedNode => selectedNode.addState("selected"));
      this.__selectedNodeUIs = selectedNodeUIs;

      qx.event.message.Bus.dispatchByName("changeNodeSelection", this.getSelectedNodes());
    },

    __setSelectedAnnotations: function(selectedAnnotations) {
      this.getSelectedAnnotations().forEach(annotation => {
        if (!selectedAnnotations.includes(annotation)) {
          annotation.setSelected(false);
        }
      });
      selectedAnnotations.forEach(selectedAnnotation => selectedAnnotation.setSelected(true));
      this.__selectedAnnotations = selectedAnnotations;
    },

    __selectNode: function(activeNodeUI, isControlPressed = false) {
      if (isControlPressed) {
        const index = this.getSelectedNodeUIs().indexOf(activeNodeUI);
        if (index > -1) {
          activeNodeUI.removeState("selected");
          this.getSelectedNodeUIs().splice(index, 1);
        } else {
          activeNodeUI.addState("selected");
          this.getSelectedNodeUIs().push(activeNodeUI);
          this.__setSelectedItem(activeNodeUI.getNodeId());
        }
      } else {
        this.__setSelectedNodes([activeNodeUI]);
        this.__setSelectedAnnotations([]);
        this.__setSelectedItem(activeNodeUI.getNodeId());
      }

      qx.event.message.Bus.dispatchByName("changeNodeSelection", this.getSelectedNodes());
    },

    __selectAnnotation: function(annotation, isControlPressed = false) {
      if (isControlPressed) {
        const index = this.getSelectedAnnotations().indexOf(annotation);
        if (index > -1) {
          annotation.setSelected(false);
          this.getSelectedAnnotations().splice(index, 1);
        } else {
          annotation.setSelected(true);
          this.getSelectedAnnotations().push(annotation);
          if (this.__selectedItemId === null) {
            this.__setSelectedItem(annotation.getId());
          }
        }
      } else {
        this.__setSelectedNodes([]);
        this.__setSelectedAnnotations([annotation]);
        this.__setSelectedItem(annotation.getId());
      }
    },

    nodeSelected: function(nodeId) {
      const nodeUI = this.getNodeUI(nodeId);
      if (nodeUI && nodeUI.classname.includes("NodeUI")) {
        this.__selectNode(nodeUI);
      }
    },

    _createNodeUI: function(nodeId) {
      const node = this.__getWorkbench().getNode(nodeId);

      const nodeUI = new osparc.workbench.NodeUI(node);
      this.bind("scale", nodeUI, "scale");
      node.addListener("keyChanged", () => this.__selectNode(nodeUI), this);
      nodeUI.populateNodeLayout(this.__svgLayer);
      nodeUI.addListener("renameNode", e => this.__openNodeRenamer(e.getData()), this);
      nodeUI.addListener("markerClicked", e => this.__openMarkerEditor(e.getData()), this);
      nodeUI.addListener("infoNode", e => this.__openNodeInfo(e.getData()), this);
      nodeUI.addListener("removeNode", e => this.fireDataEvent("removeNode", e.getData()), this);

      return nodeUI;
    },

    __edgeRepresentationExists: function(edge) {
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

          this._createEdgeBetweenNodes(nodeAId, nodeBId, true);
          this.__removeTempEdge();
          this.__removePointerMoveListener();
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
          if (srvCat) {
            this.__tempEdgeIsInput === true ? srvCat.setContext(null, dragNodeId) : srvCat.setContext(dragNodeId, null);
            srvCat.addListener("close", () => this.__removeTempEdge(), this);
          } else {
            this.__removeTempEdge();
          }
        }
        this.__removePointerMoveListener();
      }, this);
    },

    _createEdgeBetweenNodes: function(node1Id, node2Id, autoConnect = true) {
      const edge = this.__getWorkbench().createEdge(null, node1Id, node2Id, autoConnect);
      if (!edge) {
        return;
      }
      if (this.__edgeRepresentationExists(edge)) {
        return;
      }

      // build representation
      const nodeUI1 = this.getNodeUI(node1Id);
      const nodeUI2 = this.getNodeUI(node2Id);
      if (nodeUI1.getCurrentBounds() === null || nodeUI2.getCurrentBounds() === null) {
        console.error("bounds not ready");
        return;
      }

      const port1 = nodeUI1.getOutputPort();
      const port2 = nodeUI2.getInputPort();
      if (port1 && port2) {
        nodeUI2.getNode().addInputNode(node1Id);
        const pointList = this.__getEdgePoints(nodeUI1, port1, nodeUI2, port2);
        const x1 = pointList[0] ? pointList[0][0] : 0;
        const y1 = pointList[0] ? pointList[0][1] : 0;
        const x2 = pointList[1] ? pointList[1][0] : 0;
        const y2 = pointList[1] ? pointList[1][1] : 0;
        const edgeRepresentation = this.__svgLayer.drawCurve(x1, y1, x2, y2, !edge.isPortConnected());

        const edgeUI = new osparc.workbench.EdgeUI(edge, edgeRepresentation);
        this.__edgesUI.push(edgeUI);

        const hint = edgeUI.getHint();
        const that = this;
        [
          edgeRepresentation.widerCurve.node,
          edgeRepresentation.node
        ].forEach(svgEl => {
          svgEl.addEventListener("click", e => {
            // this is needed to get out of the context of svg
            that.__setSelectedItem(edgeUI.getEdgeId()); // eslint-disable-line no-underscore-dangle
            e.stopPropagation();
          }, this);

          const topOffset = 20;
          [
            "mouseover",
            "mousemove"
          ].forEach(ev => {
            svgEl.addEventListener(ev, e => {
              const leftOffset = -(parseInt(hint.getHintBounds().width/2));
              const properties = {
                top: e.clientY + topOffset,
                left: e.clientX + leftOffset
              };
              hint.setLayoutProperties(properties);
              if (hint.getText()) {
                hint.show();
              }
            }, this);
          });
        });
        edgeUI.getRepresentation().widerCurve.node.addEventListener("mouseout", () => hint.exclude(), this);
        this.__svgLayer.addListener("mouseout", () => hint.exclude(), this);
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
        const edgeUI = this.__getEdgeUI(edgeId);
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
          osparc.workbench.SvgWidget.updateCurve(edgeUI.getRepresentation(), x1, y1, x2, y2);
        }
      });
    },

    __updateIteratorShadows: function(nodeUI) {
      if ("shadows" in nodeUI) {
        const shadowDiffX = -5;
        const shadowDiffY = +3;
        const pos = nodeUI.getNode().getPosition();
        const nShadows = nodeUI.shadows.length;
        for (let i=0; i<nShadows; i++) {
          osparc.wrapper.Svg.updateItemPos(nodeUI.shadows[i], pos.x + (nShadows-i)*shadowDiffX, pos.y + (nShadows-i)*shadowDiffY);
        }
      }
    },

    __updateNodeUIPos: function(nodeUI) {
      this.__updateEdges(nodeUI);
      if (nodeUI.getNode && nodeUI.getNode().isIterator()) {
        this.__updateIteratorShadows(nodeUI);
      }

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
      return {
        x: e.getDocumentLeft() - leftOffset,
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
        osparc.workbench.SvgWidget.updateCurve(this.__tempEdgeRepr, x1, y1, x2, y2);
      }
      const portLabel = port.isInput ? nodeUI.getInputPort() : nodeUI.getOutputPort();
      portLabel.setSource(osparc.workbench.BaseNodeUI.PORT_CONNECTED);

      if (!this.__tempEdgeIsInput) {
        const modified = nodeUI.getNode().getStatus().getModified();
        const colorHex = osparc.workbench.EdgeUI.getEdgeColor(modified);
        osparc.wrapper.Svg.updateCurveColor(this.__tempEdgeRepr, colorHex);
      }
    },

    __removeTempEdge: function() {
      if (this.__tempEdgeRepr !== null) {
        osparc.wrapper.Svg.removeCurve(this.__tempEdgeRepr);
      }

      const nodeUI = this.getNodeUI(this.__tempEdgeNodeId);
      if (nodeUI) {
        const isConnected = this.__tempEdgeIsInput ? nodeUI.getNode().getInputConnected() : nodeUI.getNode().getOutputConnected();
        const portLabel = this.__tempEdgeIsInput ? nodeUI.getInputPort() : nodeUI.getOutputPort();
        portLabel.set({
          source: isConnected ? osparc.workbench.BaseNodeUI.PORT_CONNECTED : osparc.workbench.BaseNodeUI.PORT_DISCONNECTED
        });
      }

      this.__tempEdgeRepr = null;
      this.__tempEdgeNodeId = null;
      this.__tempEdgeIsInput = null;
      this.__pointerPos = null;
    },

    __removePointerMoveListener: function() {
      qx.bom.Element.removeListener(
        this.__desktop,
        "pointermove",
        this.__updateTempEdge,
        this
      );
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
      nodeUI.removeShadows();
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
        osparc.wrapper.Svg.removeCurve(edge.getRepresentation());
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

    __clearAnnotation: function(annotation) {
      if (annotation) {
        if (annotation.getRepresentation()) {
          osparc.wrapper.Svg.removeItem(annotation.getRepresentation());
        }
        if (annotation.getId() in this.__annotations) {
          delete this.__annotations[annotation.getId()];
        }
      }
    },

    __clearAllAnnotations: function() {
      while (Object.keys(this.__annotations).length > 0) {
        const keys = Object.keys(this.__annotations);
        this.__clearAnnotation(this.__annotations[keys[keys.length - 1]]);
      }
    },

    _clearAll: function() {
      this.__clearAllNodes();
      this.__clearAllEdges();
      this.__clearAllAnnotations();
    },

    __reloadCurrentModel: function() {
      if (this._currentModel) {
        this.loadModel(this.getStudy().getWorkbench());
      }
    },

    loadModel: function(model) {
      if (this.__svgLayer.getReady()) {
        this._loadModel(model);
      } else {
        this.__svgLayer.addListenerOnce("SvgWidgetReady", () => this._loadModel(model), this);
      }
    },

    _loadModel: async function(model) {
      this._clearAll();
      this._currentModel = model;
      if (model) {
        // create nodes
        const nodes = model.getNodes();
        this.__renderNodes(nodes);
        qx.ui.core.queue.Layout.flush();
        this.__renderAnnotations(model.getStudy().getUi());
      }
    },

    __renderNodes: function(nodes) {
      let nNodesToRender = Object.keys(nodes).length;
      const nodeUIs = [];
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        const nodeUI = this._createNodeUI(nodeId);
        nodeUI.addListenerOnce("appear", () => {
          nNodesToRender--;
          if (nNodesToRender === 0) {
            this.__renderEdges(nodes);
          }
        }, this);
        this._addNodeUIToWorkbench(nodeUI, node.getPosition());
        nodeUIs.push(nodeUI);
      }
      nodeUIs.forEach(nodeUI => this.__createDragDropMechanism(nodeUI));
    },

    __renderEdges: async function(nodes) {
      // create edges
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        const inputNodeIDs = node.getInputNodes();
        inputNodeIDs.forEach(inputNodeId => {
          if (inputNodeId in nodes) {
            this._createEdgeBetweenNodes(inputNodeId, nodeId, false);
          }
        });
      }
    },

    __renderAnnotations: function(studyUI) {
      const initData = studyUI.getAnnotationsInitData();
      const annotations = initData ? initData : studyUI.getAnnotations();
      Object.entries(annotations).forEach(([annotationId, annotation]) => {
        if (annotation instanceof osparc.workbench.Annotation) {
          this.__addAnnotation(annotation.serialize(), annotationId);
        } else {
          this.__addAnnotation(annotation, annotationId);
        }
      });
      if (initData) {
        studyUI.nullAnnotationsInitData();
      }
    },

    __setSelectedItem: function(newID) {
      const oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemAnEdge()) {
          const edge = this.__getEdgeUI(oldId);
          edge.setSelected(false);
        } else if (this.__isSelectedItemAnAnnotation()) {
          const annotation = this.__getAnnotation(oldId);
          annotation.setSelected(false);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemAnEdge()) {
        const edge = this.__getEdgeUI(newID);
        edge.setSelected(true);
      } else if (this.__isSelectedItemAnAnnotation()) {
        const annotation = this.__getAnnotation(newID);
        this.__setSelectedAnnotations([annotation]);
        const annotationEditor = this.__getAnnotationEditorView();
        annotationEditor.setAnnotation(annotation);
        annotationEditor.makeItModal();
        annotationEditor.addListener("deleteAnnotation", () => {
          annotationEditor.exclude();
          this.__removeAnnotation(annotation.getId());
          this.resetSelection();
        }, this);
        annotation.addListener("changeColor", e => this.__annotationLastColor = e.getData());
      } else {
        this.fireDataEvent("changeSelectedNode", newID);
      }

      if (this.__deleteItemButton) {
        this.__deleteItemButton.setVisibility(this.__isSelectedItemAnEdge() ? "visible" : "excluded");
      }
    },

    __isSelectedItemAnEdge: function() {
      return Boolean(this.__selectedItemId && this.__getEdgeUI(this.__selectedItemId));
    },

    __isSelectedItemAnAnnotation: function() {
      return Object.keys(this.__annotations).includes(this.__selectedItemId);
    },

    __getAnnotation: function() {
      return this.__isSelectedItemAnAnnotation() ? this.__annotations[this.__selectedItemId] : null;
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
      const wbPos = this.__pointerEventToWorkbenchPos(e);
      const nodeUI = this.__cursorOnNodeUI(wbPos);
      const actions = {
        addService: {
          "text": "\uf067", // plus
          "action": () => this.__openServiceCatalog(e)
        },
        zoomIn: {
          "text": "\uf00e", // search-plus
          "action": () => {
            this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
            this.zoom(true);
          }
        },
        zoomReset: {
          "text": "\uf002", // search
          "action": () => this.setScale(1)
        },
        zoomOut: {
          "text": "\uf010", // search-minus
          "action": () => {
            this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
            this.zoom(false);
          }
        },
        drawText: {
          "text": "\uf040", // pencil
          "action": () => {
            const pointerPos = this.__pointerEventToWorkbenchPos(e);
            this.startAnnotationsText(pointerPos);
          }
        },
        drawRect: {
          "text": "\uf044", // brush with rect
          "action": () => this.startAnnotationsRect()
        },
        removeNode: {
          "text": "\uf014", // trash
          "action": () => nodeUI.fireDataEvent("removeNode", nodeUI.getNodeId())
        },
        startDynService: {
          "text": "\uf04b", // play
          "action": () => nodeUI.getNode().requestStartNode()
        },
        stopDynService: {
          "text": "\uf04d", // stop
          "action": () => nodeUI.getNode().requestStopNode(true)
        },
        addRemoveMarker: {
          "text": "\uf097", // marker
          "action": () => nodeUI.getNode().toggleMarker()
        },
        addServiceInput: {
          "text": "\uf090", // in
          "action": () => {
            const freePos = this.getStudy().getWorkbench().getFreePosition(nodeUI.getNode(), true);
            const srvCat = this.openServiceCatalog({
              x: 50,
              y: 50
            }, freePos);
            if (srvCat) {
              srvCat.setContext(null, nodeUI.getNodeId());
            }
          }
        },
        addServiceOutput: {
          "text": "\uf08b", // out
          "action": () => {
            const freePos = this.getStudy().getWorkbench().getFreePosition(nodeUI.getNode(), false);
            const srvCat = this.openServiceCatalog({
              x: 50,
              y: 50
            }, freePos);
            if (srvCat) {
              srvCat.setContext(nodeUI.getNodeId(), null);
            }
          }
        },
        noAction: {
          "text": "\uf05e", // verboten
          "action": () => {}
        }
      };
      let buttons = [];
      if (nodeUI) {
        const node = nodeUI.getNode();
        if (node.isDynamic()) {
          const status = node.getStatus().getInteractive();
          if (["idle", "failed"].includes(status)) {
            buttons.push(actions.startDynService);
          } else if (["ready"].includes(status)) {
            buttons.push(actions.stopDynService);
          }
        }
        if (buttons.length === 0) {
          buttons.push(actions.addRemoveMarker);
        }
        buttons = buttons.concat([
          node.hasOutputs() ? actions.addServiceOutput : actions.noAction,
          actions.removeNode,
          node.hasInputs() ? actions.addServiceInput : actions.noAction
        ]);
      } else {
        buttons = [
          actions.addService,
          actions.drawText,
          actions.drawRect
        ];
      }
      this.__buttonsToContextMenu(e, buttons);
    },

    __buttonsToContextMenu: function(e, buttons) {
      if (this.__contextMenu) {
        this.__contextMenu.hide();
      }
      let rotation = 3 * Math.PI / 2;
      rotation -= (2/buttons.length) * (Math.PI / 2);
      const radialMenuWrapper = osparc.wrapper.RadialMenu.getInstance();
      const contextMenu = this.__contextMenu = radialMenuWrapper.createMenu({rotation});
      contextMenu.addButtons(buttons);
      contextMenu.setPos(e.getDocumentLeft() - contextMenu.w2, e.getDocumentTop() - contextMenu.h2);
      contextMenu.show();
    },

    __mouseDown: function(e) {
      if (e.isMiddlePressed()) {
        this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
        this.__panning = true;
        this.set({
          cursor: "move"
        });
      } else if (e.isRightPressed()) {
        this.__openContextMenu(e);
      }
    },

    __mouseDownOnSVG: function(e) {
      if (e.isLeftPressed()) {
        if (this.__annotatingNote || this.__annotatingRect || this.__annotatingText) {
          this.__annotationInitPos = this.__pointerEventToWorkbenchPos(e);
        } else {
          this.__selectionRectInitPos = this.__pointerEventToWorkbenchPos(e);
        }
      }
    },

    __mouseMove: function(e) {
      if (this.__isDraggingLink) {
        this.__draggingLink(e, true);
      } else if (this.__tempEdgeRepr === null && (this.__annotatingNote || this.__annotatingRect || this.__annotatingText) && this.__annotationInitPos && e.isLeftPressed()) {
        this.__drawingAnnotation(e);
      } else if (this.__tempEdgeRepr === null && this.__selectionRectInitPos && e.isLeftPressed()) {
        this.__drawingSelectionRect(e);
      } else if (this.__panning && e.isMiddlePressed()) {
        const oldPos = this.__pointerPos;
        const newPos = this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
        const moveX = parseInt((oldPos.x-newPos.x) * this.getScale());
        const moveY = parseInt((oldPos.y-newPos.y) * this.getScale());
        this._workbenchLayoutScroll.scrollToX(this._workbenchLayoutScroll.getScrollX() + moveX);
        this._workbenchLayoutScroll.scrollToY(this._workbenchLayoutScroll.getScrollY() + moveY);
        this.set({
          cursor: "move"
        });
      }
    },

    __mouseUp: function(e) {
      if (this.__selectionRectInitPos) {
        this.__selectionRectInitPos = null;
      }
      if (this.__selectionRectRepr) {
        osparc.wrapper.Svg.removeItem(this.__selectionRectRepr);
        this.__selectionRectRepr = null;
      }

      const annotationInitPos = osparc.utils.Utils.deepCloneObject(this.__annotationInitPos);
      if (this.__annotationInitPos) {
        this.__annotationInitPos = null;
      }
      if (this.__annotatingNote || this.__annotatingRect || this.__annotatingText) {
        let annotationType = null;
        if (this.__annotatingNote) {
          annotationType = "note";
        } else if (this.__annotatingRect) {
          annotationType = "rect";
        } else if (this.__annotatingText) {
          annotationType = "text";
        }
        if (this.__consolidateAnnotation(annotationType, annotationInitPos, this.__rectAnnotationRepr)) {
          if (this.__rectAnnotationRepr) {
            osparc.wrapper.Svg.removeItem(this.__rectAnnotationRepr);
            this.__rectAnnotationRepr = null;
          }
          this.__annotatingNote = false;
          this.__annotatingRect = false;
          this.__annotatingText = false;
          this.__toolHint.setValue(null);
        }
      }

      if (this.__panning) {
        this.__panning = false;
        this.set({
          cursor: "auto"
        });
      } else if (this.__isDraggingLink) {
        this.__dropLink(e);
      }

      this.activate();
    },

    __mouseWheel: function(e) {
      this.__pointerPos = this.__pointerEventToWorkbenchPos(e);
      const zoomIn = e.getWheelDelta() < 0;
      this.zoom(zoomIn);
    },

    zoom: function(zoomIn = true) {
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
      const nodesWidth = nodeBounds.right + osparc.workbench.NodeUI.NODE_WIDTH;
      const nodesHeight = nodeBounds.bottom + osparc.workbench.NodeUI.NODE_HEIGHT;
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

    _fitScaleToNodes: function(maxScale = 1.0) {
      const xFit = this.getBounds().width / this._currentModel.getFarthestPosition().x;
      const yFit = this.getBounds().height / this._currentModel.getFarthestPosition().y;

      const prefScale = Math.min(Math.min(xFit, yFit), maxScale);

      // reverse mutates original. make a copy first
      const closestDown = this.self().ZOOM_VALUES.slice().reverse().find(z => z <= prefScale);
      this.setScale(closestDown);
    },

    startAnnotationsNote: function() {
      this.__annotatingNote = true;
      this.__annotatingRect = false;
      this.__annotatingText = false;
      this.__toolHint.setValue(this.tr("Pick the position"));
    },

    startAnnotationsRect: function() {
      this.__annotatingNote = false;
      this.__annotatingRect = true;
      this.__annotatingText = false;
      this.__toolHint.setValue(this.tr("Draw a rectangle"));
    },

    startAnnotationsText: function(workbenchPos) {
      this.__annotatingNote = false;
      this.__annotatingText = true;
      this.__annotatingRect = false;
      if (workbenchPos) {
        this.__annotationInitPos = workbenchPos;
        this.__mouseUp();
      } else {
        this.__toolHint.setValue(this.tr("Pick the position"));
      }
    },

    __openNodeRenamer: function(nodeId) {
      const node = this.getStudy().getWorkbench().getNode(nodeId);
      const treeItemRenamer = new osparc.widget.Renamer(node.getLabel());
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

    __openMarkerEditor: function(nodeId) {
      if (nodeId) {
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        const marker = node.getMarker();
        if (marker) {
          const annotationEditor = this.__getAnnotationEditorView();
          annotationEditor.setMarker(marker);
          annotationEditor.makeItModal();
        }
      }
    },

    __openNodeInfo: function(nodeId) {
      if (nodeId) {
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        const serviceDetails = new osparc.info.ServiceLarge(node.getMetaData(), {
          nodeId,
          label: node.getLabel(),
          studyId: this.getStudy().getUuid()
        });
        const title = this.tr("Service information");
        const width = osparc.info.CardLarge.WIDTH;
        const height = osparc.info.CardLarge.HEIGHT;
        osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
      }
    },

    _addEventListeners: function() {
      this.addListener("appear", () => {
        this.addListener("resize", () => this.__updateAllEdges(), this);
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

        this.addListener("mousedown", this.__mouseDown, this);
        this.addListener("mousemove", this.__mouseMove, this);
        this.addListener("mouseup", this.__mouseUp, this);
        this._listenToMouseWheel();
      });

      this.addListener("keypress", keyEvent => {
        const selectedNodeIDs = this.getSelectedNodeIDs();
        switch (keyEvent.getKeyIdentifier()) {
          case "F2":
            if (selectedNodeIDs.length === 1) {
              this.__openNodeRenamer(selectedNodeIDs[0]);
            }
            break;
          case "I":
            if (selectedNodeIDs.length === 1) {
              this.__openNodeInfo(selectedNodeIDs[0]);
            }
            break;
          case "Delete":
            if (selectedNodeIDs.length === 1) {
              this.fireDataEvent("removeNode", selectedNodeIDs[0]);
            } else if (selectedNodeIDs.length) {
              this.fireDataEvent("removeNodes", selectedNodeIDs);
            } else if (this.__isSelectedItemAnEdge()) {
              this.__removeEdge(this.__getEdgeUI(this.__selectedItemId));
              this.resetSelection();
            }
            break;
          case "Escape":
            this.resetSelection();
            this.__removeTempEdge();
            this.__removePointerMoveListener();
            break;
        }
      }, this);

      this.__workbenchLayout.addListener("tap", () => this.resetSelection(), this);
      this.__workbenchLayout.addListener("dbltap", e => this.__openServiceCatalog(e), this);
      this.__workbenchLayout.addListener("resize", () => this.__updateHint(), this);

      this.__svgLayer.addListener("mousedown", this.__mouseDownOnSVG, this);
    },

    _listenToMouseWheel: function() {
      this.addListener("mousewheel", this.__mouseWheel, this);
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
      if (this.__dropHereNodeUI === null) {
        const dropHereNodeUI = this.__dropHereNodeUI = new qx.ui.basic.Label(this.tr("Drop here")).set({
          font: "workbench-start-hint",
          textColor: "workbench-start-hint"
        });
        dropHereNodeUI.exclude();
        this.__workbenchLayout.add(dropHereNodeUI);
        dropHereNodeUI.rect = this.__svgLayer.drawDashedRect(boxWidth, boxHeight);
      }
      const dropMe = this.__dropHereNodeUI;
      if (dragging) {
        dropMe.show();
        const dropMeBounds = dropMe.getBounds() || dropMe.getSizeHint();
        dropMe.setLayoutProperties({
          left: posX - parseInt(dropMeBounds.width/2) - parseInt(boxWidth/2),
          top: posY - parseInt(dropMeBounds.height/2)- parseInt(boxHeight/2)
        });
        if ("rect" in dropMe) {
          osparc.wrapper.Svg.updateItemPos(dropMe.rect, posX - boxWidth, posY - boxHeight);
        }
      } else {
        this.__removeDropHint();
      }
    },

    __drawingSelectionRect: function(e) {
      // draw rect
      const initPos = this.__selectionRectInitPos;
      const currentPos = this.__pointerEventToWorkbenchPos(e);
      const x = Math.min(initPos.x, currentPos.x);
      const y = Math.min(initPos.y, currentPos.y);
      const width = Math.abs(initPos.x - currentPos.x);
      const height = Math.abs(initPos.y - currentPos.y);
      if (this.__selectionRectRepr === null) {
        this.__selectionRectRepr = this.__svgLayer.drawFilledRect(width, height, x, y);
      } else {
        osparc.wrapper.Svg.updateRect(this.__selectionRectRepr, width, height, x, y);
      }

      // select nodes
      const nodeUIs = [];
      this.__nodesUI.forEach(nodeUI => {
        const nodeBounds = nodeUI.getCurrentBounds();
        if (nodeBounds) {
          const nodePos = nodeUI.getNode().getPosition();
          const nodePosX = nodePos.x + nodeBounds.width/2;
          const nodePosY = nodePos.y + nodeBounds.height/2;
          if (
            nodePosX > x &&
            nodePosX < x+width &&
            nodePosY > y &&
            nodePosY < y+height
          ) {
            nodeUIs.push(nodeUI);
          }
        }
      });
      this.__setSelectedNodes(nodeUIs);

      // select annotations
      const annotations = [];
      Object.keys(this.__annotations).forEach(annotationId => {
        const annotation = this.__annotations[annotationId];
        const attrs = annotation.getAttributes();
        const annotationPosX = parseInt(attrs.x) + parseInt(attrs.width/2);
        const annotationPosY = parseInt(attrs.y) + parseInt(attrs.height/2);
        if (
          annotationPosX > x &&
          annotationPosX < x+width &&
          annotationPosY > y &&
          annotationPosY < y+height
        ) {
          annotations.push(annotation);
        }
      });
      this.__setSelectedAnnotations(annotations);
    },

    __drawingAnnotation: function(e) {
      // draw rect
      const initPos = this.__annotationInitPos;
      const currentPos = this.__pointerEventToWorkbenchPos(e);
      const x = Math.min(initPos.x, currentPos.x);
      const y = Math.min(initPos.y, currentPos.y);
      const width = Math.abs(initPos.x - currentPos.x);
      const height = Math.abs(initPos.y - currentPos.y);
      if ([null, undefined].includes(this.__rectAnnotationRepr)) {
        const color = this.__annotationLastColor ? this.__annotationLastColor : osparc.workbench.Annotation.DEFAULT_COLOR;
        this.__rectAnnotationRepr = this.__svgLayer.drawAnnotationRect(width, height, x, y, color);
      } else {
        osparc.wrapper.Svg.updateRect(this.__rectAnnotationRepr, width, height, x, y);
      }
    },

    __consolidateAnnotation: function(type, initPos, annotation) {
      const color = this.__annotationLastColor ? this.__annotationLastColor : osparc.workbench.Annotation.DEFAULT_COLOR;
      const serializeData = {
        type,
        color,
        attributes: {}
      };
      if (type === "rect") {
        if ([null, undefined].includes(annotation)) {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Draw a rectangle first"), "WARNING");
          return false;
        }
        serializeData.attributes = osparc.wrapper.Svg.getRectAttributes(annotation);
      } else {
        serializeData.attributes = initPos;
      }
      if (type === "note") {
        const noteEditor = new osparc.editor.AnnotationNoteCreator();
        const win = osparc.editor.AnnotationNoteCreator.popUpInWindow(noteEditor);
        noteEditor.addListener("addNote", () => {
          const gid = noteEditor.getRecipientGid();
          osparc.store.Store.getInstance().getGroup(gid)
            .then(user => {
              serializeData.attributes.recipientGid = gid;
              serializeData.attributes.text = noteEditor.getNote();
              if (user) {
                osparc.notification.Notifications.postNewAnnotationNote(user.id, this.getStudy().getUuid());
              }
              this.__addAnnotation(serializeData);
            })
            .finally(() => win.close());
        }, this);
        noteEditor.addListener("cancel", () => win.close());
      } else if (type === "rect") {
        this.__addAnnotation(serializeData);
      } else if (type === "text") {
        const tempAnnotation = new osparc.workbench.Annotation(null, {
          type: "text",
          color,
          attributes: {
            text: "",
            fontSize: 12
          }
        });
        const annotationEditor = new osparc.editor.AnnotationEditor(tempAnnotation);
        annotationEditor.addAddButtons();
        tempAnnotation.addListener("changeColor", e => this.__annotationLastColor = e.getData());
        annotationEditor.addListener("appear", () => {
          const textField = annotationEditor.getChildControl("text-field");
          textField.focus();
          textField.activate();
        });
        const win = osparc.ui.window.Window.popUpInWindow(annotationEditor, "Add Text Annotation", 220, 135).set({
          clickAwayClose: true,
          showClose: true
        });
        annotationEditor.addListener("addAnnotation", () => {
          win.close();
          const form = annotationEditor.getForm();
          serializeData.attributes.text = form.getItem("text").getValue();
          serializeData.attributes.color = form.getItem("color").getValue();
          serializeData.color = form.getItem("color").getValue();
          serializeData.attributes.fontSize = form.getItem("size").getValue();
          this.__addAnnotation(serializeData);
        }, this);
        win.open();
      }
      return true;
    },

    __addAnnotation: function(data, id) {
      const annotation = new osparc.workbench.Annotation(this.__svgLayer, data, id);
      this.__addAnnotationListeners(annotation);
      this.__annotations[annotation.getId()] = annotation;
      this.getStudy().getUi().addAnnotation(annotation);
    },

    __removeAnnotation: function(id) {
      if (id in this.__annotations) {
        const annotation = this.__annotations[id];
        this.__clearAnnotation(annotation);
        this.getStudy().getUi().removeAnnotation(id);
      }
    },

    __dropFile: async function(e) {
      this.__draggingFile(e, false);

      if ("dataTransfer" in e) {
        this.__isDraggingFile = false;
        const files = osparc.file.FileDrop.getFilesFromEvent(e);
        if (files.length) {
          if (files.length === 1) {
            const pos = {
              x: e.offsetX,
              y: e.offsetY
            };
            const service = qx.data.marshal.Json.createModel(osparc.service.Utils.getFilePicker());
            const nodeUI = await this.__addNode(service, pos);
            if (nodeUI) {
              const filePicker = new osparc.file.FilePicker(nodeUI.getNode(), "workbench");
              filePicker.uploadPendingFiles(files);
              filePicker.addListener("fileUploaded", () => this.fireDataEvent("nodeSelected", nodeUI.getNodeId()), this);
            }
          } else {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Only one file at a time is accepted."), "ERROR");
          }
        } else {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Folders are not accepted. You might want to upload a zip file."), "ERROR");
        }
      }
    },

    __dropLink: async function(e) {
      this.__draggingLink(e, false);

      if (this.__isDraggingLink && "dragData" in this.__isDraggingLink) {
        const pos = this.__pointerEventToWorkbenchPos(e, false);
        const service = qx.data.marshal.Json.createModel(osparc.service.Utils.getFilePicker());
        const nodeUI = this.__addNode(service, pos);
        if (nodeUI) {
          const node = nodeUI.getNode();
          const data = this.__isDraggingLink["dragData"];
          osparc.file.FilePicker.setOutputValueFromStore(node, data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
          this.__isDraggingLink = null;
        }
      }
    },

    __updateHint: function() {
      if (!this.isPropertyInitialized("study") || this.__startHint === null) {
        return;
      }
      const isEmptyWorkspace = this.getStudy().isPipelineEmpty();
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
      this.__dropHereNodeUI.setVisibility("excluded");
      osparc.wrapper.Svg.removeItem(this.__dropHereNodeUI.rect);
      this.__dropHereNodeUI = null;
    }
  }
});
