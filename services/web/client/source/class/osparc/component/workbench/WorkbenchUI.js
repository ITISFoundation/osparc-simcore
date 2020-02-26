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
 *   Widget containing the layout where NodeUIs and EdgeUIs, and when the model loaded
 * is a container-node, also NodeInput and NodeOutput are rendered.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let workbenchUI = new osparc.component.workbench.WorkbenchUI(workbench);
 *   this.getRoot().add(workbenchUI);
 * </pre>
 */

const BUTTON_SIZE = 50;
const BUTTON_SPACING = 10;
const NODE_INPUTS_WIDTH = 210;

qx.Class.define("osparc.component.workbench.WorkbenchUI", {
  extend: qx.ui.core.Widget,

  /**
    * @param workbench {osparc.data.model.Workbench} Workbench owning the widget
    */
  construct: function(workbench) {
    this.base(arguments);

    this.__nodesUI = [];
    this.__edgesUI = [];
    this.__selectedNodes = [];

    const hBox = new qx.ui.layout.HBox();
    this._setLayout(hBox);

    this.setWorkbench(workbench);

    const inputNodesLayout = this.__inputNodesLayout = this.__createInputOutputNodesLayout(true);
    this._add(inputNodesLayout);

    this.__desktopCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    this._add(this.__desktopCanvas, {
      flex: 1
    });

    const nodesExposedLayout = this.__outputNodesLayout = this.__createInputOutputNodesLayout(false);
    this._add(nodesExposedLayout);

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.__desktopCanvas.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__startHint = new qx.ui.basic.Label(this.tr("Double click to start adding a node")).set({
      font: "workbench-start-hint",
      textColor: "workbench-start-hint",
      visibility: "excluded"
    });
    this.__desktopCanvas.add(this.__startHint);

    this.__svgWidgetLinks = new osparc.component.workbench.SvgWidget("SvgWidget_Links");
    this.__desktop.add(this.__svgWidgetLinks, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__svgWidgetDrop = new osparc.component.workbench.SvgWidget("SvgWidget_Drop");
    this.__svgWidgetDrop.set({
      zIndex: this.__svgWidgetLinks.getZIndex() - 1
    });
    this.__desktop.add(this.__svgWidgetDrop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    let buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(BUTTON_SPACING));
    this.__desktopCanvas.add(buttonContainer, {
      bottom: 10,
      right: 10
    });
    let unlinkButton = this.__unlinkButton = this.__getUnlinkButton();
    unlinkButton.setVisibility("excluded");
    buttonContainer.add(unlinkButton);

    this.__addEventListeners();
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
    }
  },

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "removeEdge": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
  },

  properties: {
    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false
    }
  },

  members: {
    __unlinkButton: null,
    __nodesUI: null,
    __edgesUI: null,
    __inputNodesLayout: null,
    __outputNodesLayout: null,
    __desktop: null,
    __svgWidgetLinks: null,
    __svgWidgetDrop: null,
    __tempEdgeNodeId: null,
    __tempEdgeRepr: null,
    __pointerPosX: null,
    __pointerPosY: null,
    __selectedItemId: null,
    __currentModel: null,
    __selectedNodes: null,
    __startHint: null,
    __dropHint: null,


    __getUnlinkButton: function() {
      const icon = "@FontAwesome5Solid/unlink/16";
      let unlinkBtn = new qx.ui.form.Button(null, icon);
      unlinkBtn.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      unlinkBtn.addListener("execute", function() {
        if (this.__selectedItemId && this.__isSelectedItemAnEdge()) {
          this.__removeEdge(this.__getEdgeUI(this.__selectedItemId));
          this.__selectedItemId = null;
        }
      }, this);
      return unlinkBtn;
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

    openServiceCatalog: function() {
      let srvCat = this.__createServiceCatalog();
      srvCat.open();
    },

    __createServiceCatalog: function(pos) {
      let srvCat = new osparc.component.workbench.ServiceCatalog();
      if (pos) {
        srvCat.moveTo(pos.x, pos.y);
      } else {
        // srvCat.center();
        const bounds = this.getLayoutParent().getBounds();
        const workbenchUICenter = {
          x: bounds.left + parseInt((bounds.left + bounds.width) / 2),
          y: bounds.top + parseInt((bounds.top + bounds.height) / 2)
        };
        srvCat.moveTo(workbenchUICenter.x - 200, workbenchUICenter.y - 200);
      }
      srvCat.addListener("addService", ev => {
        this.__addServiceFromCatalog(ev.getData(), pos);
      }, this);
      return srvCat;
    },

    __addServiceFromCatalog: function(data, pos) {
      const service = data.service;
      let nodeAId = "contextNodeId" in data ? data.contextNodeId : null;
      let portA = "contextPort" in data ? data.contextPort : null;

      let parent = null;
      if (this.__currentModel.isContainer()) {
        parent = this.__currentModel;
      }
      const node = this.getWorkbench().createNode(service.getKey(), service.getVersion(), null, parent);
      if (!node) {
        return null;
      }

      const nodeUI = this.__createNodeUI(node.getNodeId());
      this.__addNodeToWorkbench(nodeUI, pos);

      if (nodeAId !== null && portA !== null) {
        let nodeBId = nodeUI.getNodeId();
        let portB = this.__findCompatiblePort(nodeUI, portA);
        // swap node-ports to have node1 as input and node2 as output
        if (portA.isInput) {
          [nodeAId, portA, nodeBId, portB] = [nodeBId, portB, nodeAId, portA];
        }
        this.__createEdgeBetweenNodes({
          nodeUuid: nodeAId
        }, {
          nodeUuid: nodeBId
        });
      }

      return nodeUI;
    },

    __addNodeToWorkbench: function(nodeUI, position) {
      if (position === undefined || position === null) {
        position = {};
        let farthestRight = 0;
        for (let i = 0; i < this.__nodesUI.length; i++) {
          let boundPos = this.__nodesUI[i].getBounds();
          let rightPos = boundPos.left + boundPos.width;
          if (farthestRight < rightPos) {
            farthestRight = rightPos;
          }
        }
        position.x = 50 + farthestRight;
        position.y = 200;
      }
      nodeUI.getNode().setPosition(position.x, position.y);
      nodeUI.moveTo(position.x, position.y);
      this.__addWindowToDesktop(nodeUI);
      this.__nodesUI.push(nodeUI);

      nodeUI.addListener("nodeMoving", function() {
        this.__updateEdges(nodeUI);
      }, this);

      nodeUI.addListener("appear", function() {
        this.__updateEdges(nodeUI);
      }, this);

      nodeUI.addListener("tap", e => {
        this.__activeNodeChanged(nodeUI, e.isCtrlPressed());
        e.stopPropagation();
      }, this);

      nodeUI.addListener("dbltap", e => {
        this.__nodeSelected(nodeUI.getNodeId());
        e.stopPropagation();
      }, this);

      qx.ui.core.queue.Layout.flush();

      this.__updateHint();
    },

    getCurrentModel: function() {
      return this.__currentModel;
    },

    getSelectedNodes: function() {
      return this.__selectedNodes;
    },

    resetSelectedNodes: function() {
      this.__selectedNodes = [];
      qx.event.message.Bus.dispatchByName("changeWorkbenchSelection", []);
    },

    __activeNodeChanged: function(activeNode, isControlPressed = false) {
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

    __createNodeUI: function(nodeId) {
      let node = this.getWorkbench().getNode(nodeId);

      let nodeUI = new osparc.component.workbench.NodeUI(node);
      nodeUI.populateNodeLayout();
      this.__createDragDropMechanism(nodeUI);

      return nodeUI;
    },

    __createEdgeUI: function(node1Id, node2Id, edgeId) {
      const edge = this.getWorkbench().createEdge(edgeId, node1Id, node2Id);
      if (!edge) {
        return null;
      }
      if (this.__edgeRepresetationExists(edge)) {
        return null;
      }

      // build representation
      const nodeUI1 = this.getNodeUI(node1Id);
      const nodeUI2 = this.getNodeUI(node2Id);
      const port1 = nodeUI1.getOutputPort();
      const port2 = nodeUI2.getInputPort();
      if (port1 && port2) {
        if (this.__currentModel.isContainer() && nodeUI2.getNodeId() === this.__currentModel.getNodeId()) {
          this.__currentModel.addOutputNode(nodeUI1.getNodeId());
        } else {
          nodeUI2.getNode().addInputNode(node1Id);
        }
        const pointList = this.__getEdgePoints(nodeUI1, port1, nodeUI2, port2);
        const x1 = pointList[0] ? pointList[0][0] : 0;
        const y1 = pointList[0] ? pointList[0][1] : 0;
        const x2 = pointList[1] ? pointList[1][0] : 0;
        const y2 = pointList[1] ? pointList[1][1] : 0;
        const edgeRepresentation = this.__svgWidgetLinks.drawCurve(x1, y1, x2, y2);

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
          this.__startTempEdge,
          this
        );
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
          compatible = this.__areNodesCompatible(dragPortTarget, dropPortTarget);
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

          this.__createEdgeBetweenNodes({
            nodeUuid: nodeAId
          }, {
            nodeUuid: nodeBId
          });
          this.__removeTempEdge();
          qx.bom.Element.removeListener(
            this.__desktop,
            evType,
            this.__startTempEdge,
            this
          );
        }
      }, this);

      nodeUI.addListener("edgeDragEnd", e => {
        let data = e.getData();
        let dragNodeId = data.nodeId;

        let posX = this.__pointerPosX;
        let posY = this.__pointerPosY;
        if (this.__tempEdgeNodeId === dragNodeId) {
          const pos = {
            x: posX,
            y: posY
          };
          let srvCat = this.__createServiceCatalog(pos);
          if (this.__tempEdgeIsInput === true) {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getInputPort());
          } else {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getOutputPort());
          }
          srvCat.addListener("close", function(ev) {
            this.__removeTempEdge();
          }, this);
          srvCat.open();
        }
        qx.bom.Element.removeListener(
          this.__desktop,
          evType,
          this.__startTempEdge,
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
        const inputNode = this.getWorkbench().getNode(inputNodeId);
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

    __areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      return osparc.utils.Ports.areNodesCompatible(topLevelPort1, topLevelPort2);
    },

    __findCompatiblePort: function(nodeB, portA) {
      if (portA.isInput && nodeB.getOutputPort()) {
        return nodeB.getOutputPort();
      } else if (nodeB.getInputPort()) {
        return nodeB.getInputPort();
      }
      return null;
    },

    __createEdgeBetweenNodes: function(from, to, edgeId) {
      const node1Id = from.nodeUuid;
      const node2Id = to.nodeUuid;
      this.__createEdgeUI(node1Id, node2Id, edgeId);
    },

    __createEdgeBetweenNodesAndInputNodes: function(from, to, edgeId) {
      const inputNodes = this.__inputNodesLayout.getChildren();
      // Children[0] is the title
      for (let i = 1; i < inputNodes.length; i++) {
        const inputNodeId = inputNodes[i].getNodeId();
        if (inputNodeId === from.nodeUuid) {
          let node1Id = from.nodeUuid;
          let node2Id = to.nodeUuid;
          this.__createEdgeUI(node1Id, node2Id, edgeId);
        }
      }
    },

    __updateAllEdges: function() {
      this.__nodesUI.forEach(nodeUI => {
        this.__updateEdges(nodeUI);
      });
    },

    __updateEdges: function(nodeUI) {
      let edgesInvolved = this.getWorkbench().getConnectedEdges(nodeUI.getNodeId());

      edgesInvolved.forEach(edgeId => {
        let edgeUI = this.__getEdgeUI(edgeId);
        if (edgeUI) {
          let node1 = this.getNodeUI(edgeUI.getEdge().getInputNodeId());
          let port1 = node1.getOutputPort();
          let node2 = this.getNodeUI(edgeUI.getEdge().getOutputNodeId());
          let port2 = node2.getInputPort();
          const pointList = this.__getEdgePoints(node1, port1, node2, port2);
          const x1 = pointList[0][0];
          const y1 = pointList[0][1];
          const x2 = pointList[1][0];
          const y2 = pointList[1][1];
          this.__svgWidgetLinks.updateCurve(edgeUI.getRepresentation(), x1, y1, x2, y2);
        }
      });
    },

    __getPointEventPosition: function(pointerEvent) {
      const navBarHeight = 50;
      const inputNodesLayoutWidth = this.__inputNodesLayout.isVisible() ? this.__inputNodesLayout.getWidth() : 0;
      const x = pointerEvent.getViewportLeft() - this.getBounds().left - inputNodesLayoutWidth;
      const y = pointerEvent.getViewportTop() - navBarHeight;
      return [x, y];
    },

    __startTempEdge: function(pointerEvent) {
      if (this.__tempEdgeNodeId === null) {
        return;
      }
      let nodeUI = this.getNodeUI(this.__tempEdgeNodeId);
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

      [this.__pointerPosX, this.__pointerPosY] = this.__getPointEventPosition(pointerEvent);

      let portPos = nodeUI.getEdgePoint(port);
      if (portPos[0] === null) {
        portPos[0] = parseInt(this.__desktopCanvas.getBounds().width - 6);
      }

      let x1;
      let y1;
      let x2;
      let y2;
      if (port.isInput) {
        x1 = this.__pointerPosX;
        y1 = this.__pointerPosY;
        x2 = portPos[0];
        y2 = portPos[1];
      } else {
        x1 = portPos[0];
        y1 = portPos[1];
        x2 = this.__pointerPosX;
        y2 = this.__pointerPosY;
      }

      if (this.__tempEdgeRepr === null) {
        this.__tempEdgeRepr = this.__svgWidgetLinks.drawCurve(x1, y1, x2, y2);
      } else {
        this.__svgWidgetLinks.updateCurve(this.__tempEdgeRepr, x1, y1, x2, y2);
      }
    },

    __removeTempEdge: function() {
      if (this.__tempEdgeRepr !== null) {
        this.__svgWidgetLinks.removeCurve(this.__tempEdgeRepr);
      }
      this.__tempEdgeRepr = null;
      this.__tempEdgeNodeId = null;
      this.__pointerPosX = null;
      this.__pointerPosY = null;
    },

    __getEdgePoints: function(node1, port1, node2, port2) {
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }
      let p1 = node1.getEdgePoint(port1);
      let p2 = node2.getEdgePoint(port2);
      if (p2[0] === null) {
        p2[0] = parseInt(this.__desktopCanvas.getBounds().width - 6);
      }
      return [p1, p2];
    },

    getNodeUI: function(nodeId) {
      for (let i = 0; i < this.__nodesUI.length; i++) {
        if (this.__nodesUI[i].getNodeId() === nodeId) {
          return this.__nodesUI[i];
        }
      }
      return null;
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
      this.__clearNode(nodeId);
    },

    clearEdge: function(edgeId) {
      this.__clearEdge(this.__getEdgeUI(edgeId));
    },

    __removeEdge: function(edge) {
      this.fireDataEvent("removeEdge", edge.getEdgeId());
    },

    __clearNode: function(nodeId) {
      let nodeUI = this.getNodeUI(nodeId);
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
      while (this.__nodesUI.length > 0) {
        this.__clearNode(this.__nodesUI[this.__nodesUI.length - 1].getNodeId());
      }
    },

    __clearEdge: function(edge) {
      if (edge) {
        this.__svgWidgetLinks.removeCurve(edge.getRepresentation());
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

    clearAll: function() {
      this.__clearAllNodes();
      this.__clearAllEdges();
    },

    loadModel: function(model) {
      if (this.__svgWidgetLinks.getReady()) {
        this.__loadModel(model);
      } else {
        this.__svgWidgetLinks.addListenerOnce("SvgWidgetReady", () => {
          this.__loadModel(model);
        }, this);
      }
    },

    __loadModel: function(model) {
      this.clearAll();
      this.resetSelectedNodes();
      this.__currentModel = model;
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

        let nodes = isContainer ? model.getInnerNodes() : model.getNodes();
        for (const nodeUuid in nodes) {
          const node = nodes[nodeUuid];
          let nodeUI = this.__createNodeUI(nodeUuid);
          this.__addNodeToWorkbench(nodeUI, node.getPosition());
        }

        for (const nodeUuid in nodes) {
          const node = nodes[nodeUuid];
          const inputNodes = node.getInputNodes();
          for (let i = 0; i < inputNodes.length; i++) {
            let inputNode = inputNodes[i];
            if (inputNode in nodes) {
              this.__createEdgeBetweenNodes({
                nodeUuid: inputNode
              }, {
                nodeUuid: nodeUuid
              });
            } else {
              this.__createEdgeBetweenNodesAndInputNodes({
                nodeUuid: inputNode
              }, {
                nodeUuid: nodeUuid
              });
            }
          }
        }

        if (isContainer) {
          const outputNodes = model.getOutputNodes();
          for (let i=0; i<outputNodes.length; i++) {
            this.__createEdgeBetweenNodes({
              nodeUuid: outputNodes[i]
            }, {
              nodeUuid: model.getNodeId()
            });
          }
        }
      }
    },

    __addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();
    },

    __selectedItemChanged: function(newID) {
      const oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemAnEdge()) {
          const unselectedEdge = this.__getEdgeUI(oldId);
          const unselectedColor = osparc.theme.Color.colors["workbench-edge-comp-active"];
          this.__svgWidgetLinks.updateColor(unselectedEdge.getRepresentation(), unselectedColor);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemAnEdge()) {
        const selectedEdge = this.__getEdgeUI(newID);
        const selectedColor = osparc.theme.Color.colors["workbench-edge-selected"];
        this.__svgWidgetLinks.updateColor(selectedEdge.getRepresentation(), selectedColor);
      } else if (newID) {
        this.fireDataEvent("changeSelectedNode", newID);
      }

      this.__unlinkButton.setVisibility(this.__isSelectedItemAnEdge() ? "visible" : "excluded");
    },

    __nodeSelected: function(nodeId) {
      this.fireDataEvent("nodeDoubleClicked", nodeId);
    },

    __isSelectedItemAnEdge: function() {
      return Boolean(this.__getEdgeUI(this.__selectedItemId));
    },

    __addEventListeners: function() {
      this.addListener("appear", () => {
        // Reset filters and sidebars
        osparc.component.filter.UIFilterController.getInstance().resetGroup("workbench");
        osparc.component.filter.UIFilterController.getInstance().setContainerVisibility("workbench", "visible");

        qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", false);

        const domEl = this.getContentElement().getDomElement();
        domEl.addEventListener("dragenter", this.__dragEnter.bind(this), false);
        domEl.addEventListener("dragover", this.__dragOver.bind(this), false);
        domEl.addEventListener("dragleave", this.__dragLeave.bind(this), false);
        domEl.addEventListener("drop", this.__drop.bind(this), false);

        this.addListener("resize", () => this.__updateAllEdges(), this);
      });
      this.addListener("disappear", () => {
        // Reset filters
        osparc.component.filter.UIFilterController.getInstance().resetGroup("workbench");
        osparc.component.filter.UIFilterController.getInstance().setContainerVisibility("workbench", "excluded");
      });

      this.addListener("dbltap", e => {
        const [x, y] = this.__getPointEventPosition(e);
        const pos = {
          x,
          y
        };
        const srvCat = this.__createServiceCatalog(pos);
        srvCat.open();
      }, this);

      this.__desktopCanvas.addListener("resize", () => this.__updateHint(), this);

      this.__desktopCanvas.addListener("tap", e => {
        this.__selectedItemChanged(null);
      }, this);
    },

    __allowDrag: function(pointerEvent) {
      return (pointerEvent.target instanceof SVGElement);
    },

    __allowDrop: function(pointerEvent) {
      const files = pointerEvent.dataTransfer.files;
      if (files.length === 1) {
        return files[0].type !== "";
      }
      return false;
    },

    __dragEnter: function(e) {
      this.__dragging(e, true);
    },

    __dragOver: function(e) {
      this.__dragging(e, true);
    },

    __dragLeave: function(e) {
      this.__dragging(e, false);
    },

    __drop: function(e) {
      this.__dragging(e, false);

      if (this.__allowDrop(e)) {
        const pos = {
          x: e.offsetX,
          y: e.offsetY
        };
        const fileList = e.dataTransfer.files;
        if (fileList.length) {
          const data = {
            service: qx.data.marshal.Json.createModel(osparc.utils.Services.getFilePicker())
          };
          const nodeUI = this.__addServiceFromCatalog(data, pos);
          const filePicker = new osparc.file.FilePicker(nodeUI.getNode());
          filePicker.uploadPendingFiles(fileList);
        }
      } else {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
      }
    },

    __dragging: function(pointerEvent, dragging) {
      if (this.__allowDrag(pointerEvent)) {
        pointerEvent.preventDefault();
        pointerEvent.stopPropagation();
      } else {
        dragging = false;
      }

      if (!this.isPropertyInitialized("workbench")) {
        return;
      }
      const nodeWidth = osparc.component.workbench.NodeUI.NodeWidth;
      const nodeHeight = osparc.component.workbench.NodeUI.NodeHeight;
      const posX = pointerEvent.offsetX - 1;
      const posY = pointerEvent.offsetY - 1;

      if (this.__dropHint === null) {
        this.__dropHint = new qx.ui.basic.Label(this.tr("Drop me")).set({
          font: "workbench-start-hint",
          textColor: "workbench-start-hint",
          visibility: "excluded"
        });
        this.__desktopCanvas.add(this.__dropHint);
        this.__dropHint.rect = this.__svgWidgetDrop.drawDashedRect(nodeWidth, nodeHeight, posX, posY);
      }
      if (dragging) {
        this.__dropHint.setVisibility("visible");
        const dropBounds = this.__dropHint.getBounds() || this.__dropHint.getSizeHint();
        this.__dropHint.setLayoutProperties({
          left: posX + parseInt(nodeWidth/2) - parseInt(dropBounds.width/2),
          top: posY + parseInt(nodeHeight/2) - parseInt(dropBounds.height/2)
        });
        this.__svgWidgetDrop.updateRect(this.__dropHint.rect, posX, posY);
      } else {
        this.__dropHint.setVisibility("excluded");
        this.__svgWidgetDrop.removeRect(this.__dropHint.rect);
        this.__dropHint = null;
      }
    },

    __updateHint: function() {
      if (!this.isPropertyInitialized("workbench")) {
        return;
      }
      const isEmptyWorkspace = Object.keys(this.getWorkbench().getNodes()).length === 0;
      this.__startHint.setVisibility(isEmptyWorkspace ? "visible" : "excluded");
      if (isEmptyWorkspace) {
        const hintBounds = this.__startHint.getBounds() || this.__startHint.getSizeHint();
        const {
          height,
          width
        } = this.__desktopCanvas.getBounds();
        this.__startHint.setLayoutProperties({
          top: Math.round((height - hintBounds.height) / 2),
          left: Math.round((width - hintBounds.width) / 2)
        });
      }
    }
  }
});
