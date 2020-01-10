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
const NODE_INPUTS_WIDTH = 200;

qx.Class.define("osparc.component.workbench.WorkbenchUI", {
  extend: qx.ui.core.Widget,

  /**
    * @param workbench {osparc.data.model.Workbench} Workbench owning the widget
  */
  construct: function(workbench) {
    this.base(arguments);

    this.__nodesUI = [];
    this.__edgesUI = [];

    let hBox = new qx.ui.layout.HBox();
    this._setLayout(hBox);

    let inputNodesLayout = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    inputNodesLayout.set({
      width: NODE_INPUTS_WIDTH,
      maxWidth: NODE_INPUTS_WIDTH,
      allowGrowX: false
    });
    const navBarLabelFont = qx.bom.Font.fromConfig(osparc.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label(this.tr("Inputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);
    this._add(inputNodesLayout);

    this.__desktopCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    this._add(this.__desktopCanvas, {
      flex: 1
    });

    let nodesExposedLayout = this.__outputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    nodesExposedLayout.set({
      width: NODE_INPUTS_WIDTH,
      maxWidth: NODE_INPUTS_WIDTH,
      allowGrowX: false
    });
    let outputLabel = new qx.ui.basic.Label(this.tr("Outputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    nodesExposedLayout.add(outputLabel);
    this._add(nodesExposedLayout);

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.__desktopCanvas.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__startHint = new qx.ui.basic.Label(this.tr("Double click on this area to start")).set({
      font: "workbench-start-hint",
      textColor: "workbench-start-hint",
      visibility: "excluded"
    });
    this.__desktopCanvas.add(this.__startHint);

    this.__svgWidget = new osparc.component.workbench.SvgWidget("SvgWidgetLayer");
    // this gets fired once the widget has appeared and the library has been loaded
    // due to the qx rendering, this will always happen after setup, so we are
    // sure to catch this event
    this.__svgWidget.addListenerOnce("SvgWidgetReady", () => {
      // Will be called only the first time Svg lib is loaded
      this.removeAll();
      this.setWorkbench(workbench);
      this.__nodeSelected("root");
    });

    this.__desktop.add(this.__svgWidget, {
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

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "removeEdge": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
  },

  properties: {
    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false,
      apply: "loadModel"
    }
  },

  members: {
    __unlinkButton: null,
    __nodesUI: null,
    __edgesUI: null,
    __inputNodesLayout: null,
    __outputNodesLayout: null,
    __desktop: null,
    __svgWidget: null,
    __tempEdgeNodeId: null,
    __tempEdgeRepr: null,
    __pointerPosX: null,
    __pointerPosY: null,
    __selectedItemId: null,
    __currentModel: null,

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
        this.__addServiceFromCatalog(ev, pos);
      }, this);
      return srvCat;
    },

    __addServiceFromCatalog: function(e, pos) {
      const data = e.getData();
      const service = data.service;
      let nodeAId = data.contextNodeId;
      let portA = data.contextPort;

      let parent = null;
      if (this.__currentModel.isContainer()) {
        parent = this.__currentModel;
      }
      const node = this.getWorkbench().createNode(service.getKey(), service.getVersion(), null, parent);
      if (!node) {
        return;
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
      this.addWindowToDesktop(nodeUI);
      this.__nodesUI.push(nodeUI);

      nodeUI.addListener("nodeMoving", function() {
        this.__updateEdges(nodeUI);
        this.__updatePosition(nodeUI);
      }, this);

      nodeUI.addListener("appear", function() {
        this.__updateEdges(nodeUI);
      }, this);

      nodeUI.addListener("tap", e => {
        this.__selectedItemChanged(nodeUI.getNodeId());
        e.stopPropagation();
      }, this);

      nodeUI.addListener("dbltap", e => {
        this.__nodeSelected(nodeUI.getNodeId());
        e.stopPropagation();
      }, this);

      qx.ui.core.queue.Layout.flush();

      this.__updateHint();
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
          nodeUI1.getNode().setIsOutputNode(true);
        } else {
          nodeUI2.getNode().addInputNode(node1Id);
        }
        const pointList = this.__getEdgePoints(nodeUI1, port1, nodeUI2, port2);
        const x1 = pointList[0] ? pointList[0][0] : 0;
        const y1 = pointList[0] ? pointList[0][1] : 0;
        const x2 = pointList[1] ? pointList[1][0] : 0;
        const y2 = pointList[1] ? pointList[1][1] : 0;
        const edgeRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);

        const edgeUI = new osparc.component.workbench.EdgeUI(edge, edgeRepresentation);
        this.__edgesUI.push(edgeUI);

        edgeUI.getRepresentation().node.addEventListener("click", e => {
          // this is needed to get out of the context of svg
          edgeUI.fireDataEvent("edgeSelected", edgeUI.getEdgeId());
          e.stopPropagation();
        }, this);

        edgeUI.addListener("edgeSelected", e => {
          this.__selectedItemChanged(edgeUI.getEdgeId());
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
      const inputNodes = model.getInputNodes();
      for (let i = 0; i < inputNodes.length; i++) {
        let inputNode = this.getWorkbench().getNode(inputNodes[i]);
        let inputLabel = this.__createNodeInputUI(inputNode);
        this.__nodesUI.push(inputLabel);
      }
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
      let outputLabel = this.__createNodeOutputUI(model);
      this.__nodesUI.push(outputLabel);
    },

    __clearNodeOutputUIs: function() {
      // remove all but the title
      while (this.__outputNodesLayout.getChildren().length > 1) {
        this.__outputNodesLayout.removeAt(this.__outputNodesLayout.getChildren().length - 1);
      }
    },

    __removeSelectedNode: function() {
      for (let i = 0; i < this.__nodesUI.length; i++) {
        if (this.__desktop.getActiveWindow() === this.__nodesUI[i]) {
          this.__removeNode(this.__nodesUI[i]);
          return;
        }
      }
    },

    __areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      return osparc.utils.Services.areNodesCompatible(topLevelPort1, topLevelPort2);
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

    __updatePosition: function(nodeUI) {
      const cBounds = nodeUI.getCurrentBounds();
      const node = this.getWorkbench().getNode(nodeUI.getNodeId());
      node.setPosition(cBounds.left, cBounds.top);
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
          this.__svgWidget.updateCurve(edgeUI.getRepresentation(), x1, y1, x2, y2);
        }
      });
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

      const navBarHeight = 50;
      const inputNodesLayoutWidth = this.__inputNodesLayout.isVisible() ? this.__inputNodesLayout.getWidth() : 0;
      this.__pointerPosX = pointerEvent.getViewportLeft() - this.getBounds().left - inputNodesLayoutWidth;
      this.__pointerPosY = pointerEvent.getViewportTop() - navBarHeight;

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
        this.__tempEdgeRepr = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      } else {
        this.__svgWidget.updateCurve(this.__tempEdgeRepr, x1, y1, x2, y2);
      }
    },

    __removeTempEdge: function() {
      if (this.__tempEdgeRepr !== null) {
        this.__svgWidget.removeCurve(this.__tempEdgeRepr);
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

    __removeNode: function(node) {
      this.fireDataEvent("removeNode", node.getNodeId());
    },

    clearNode(nodeId) {
      this.__clearNode(nodeId);
    },

    __removeAllNodes: function() {
      while (this.__nodesUI.length > 0) {
        this.__removeNode(this.__nodesUI[this.__nodesUI.length - 1]);
      }
    },

    clearEdge: function(edgeId) {
      this.__clearEdge(this.__getEdgeUI(edgeId));
    },

    __removeEdge: function(edge) {
      this.fireDataEvent("removeEdge", edge.getEdgeId());
    },

    __removeAllEdges: function() {
      while (this.__edgesUI.length > 0) {
        this.__removeEdge(this.__edgesUI[this.__edgesUI.length - 1]);
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllEdges();
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
      this.__svgWidget.removeCurve(edge.getRepresentation());
      let index = this.__edgesUI.indexOf(edge);
      if (index > -1) {
        this.__edgesUI.splice(index, 1);
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
      this.clearAll();
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
              if (!isContainer) {
                console.log("Shouldn't be the case");
              }
              this.__createEdgeBetweenNodesAndInputNodes({
                nodeUuid: inputNode
              }, {
                nodeUuid: nodeUuid
              });
            }
          }
        }

        const innerNodes = isContainer ? model.getInnerNodes() : {};
        for (const innerNodeId in innerNodes) {
          const innerNode = innerNodes[innerNodeId];
          if (innerNode.getIsOutputNode()) {
            this.__createEdgeBetweenNodes({
              nodeUuid: innerNode.getNodeId()
            }, {
              nodeUuid: model.getNodeId()
            });
          }
        }
      }
    },

    addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();
    },

    __selectedItemChanged: function(newID) {
      const oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemAnEdge()) {
          const unselectedEdge = this.__getEdgeUI(oldId);
          const unselectedColor = osparc.theme.Color.colors["workbench-edge-comp-active"];
          this.__svgWidget.updateColor(unselectedEdge.getRepresentation(), unselectedColor);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemAnEdge()) {
        const selectedEdge = this.__getEdgeUI(newID);
        const selectedColor = osparc.theme.Color.colors["workbench-edge-selected"];
        this.__svgWidget.updateColor(selectedEdge.getRepresentation(), selectedColor);
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
      });
      this.addListener("disappear", () => {
        // Reset filters
        osparc.component.filter.UIFilterController.getInstance().resetGroup("workbench");
        osparc.component.filter.UIFilterController.getInstance().setContainerVisibility("workbench", "excluded");
      });

      this.__desktop.addListener("tap", e => {
        this.__selectedItemChanged(null);
      }, this);

      this.addListener("dbltap", e => {
        const x = e.getViewportLeft() - this.getBounds().left;
        const y = e.getViewportTop();
        const pos = {
          x: x,
          y: y
        };
        const srvCat = this.__createServiceCatalog(pos);
        srvCat.open();
      }, this);

      this.__desktopCanvas.addListener("resize", () => this.__updateHint(), this);
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
