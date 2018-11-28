/* eslint no-warning-comments: "off" */
/* global window */

const BUTTON_SIZE = 50;
const BUTTON_SPACING = 10;
const NODE_INPUTS_WIDTH = 200;

qx.Class.define("qxapp.component.workbench.WorkbenchView", {
  extend: qx.ui.container.Composite,

  construct: function(workbenchModel) {
    this.base();

    let hBox = new qx.ui.layout.HBox();
    this.set({
      layout: hBox
    });

    let inputNodesLayout = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    inputNodesLayout.set({
      width: NODE_INPUTS_WIDTH,
      maxWidth: NODE_INPUTS_WIDTH,
      allowGrowX: false
    });
    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label(this.tr("Inputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);
    this.add(inputNodesLayout);

    this.__desktopCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    this.add(this.__desktopCanvas, {
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
    this.add(nodesExposedLayout);

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.__desktopCanvas.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.setWorkbenchModel(workbenchModel);
    this.__svgWidget = new qxapp.component.workbench.SvgWidget("SvgWidgetLayer");
    // this gets fired once the widget has appeared and the library has been loaded
    // due to the qx rendering, this will always happen after setup, so we are
    // sure to catch this event
    this.__svgWidget.addListenerOnce("SvgWidgetReady", () => {
      // Will be called only the first time Svg lib is loaded
      this.removeAll();
      this.loadModel(this.getWorkbenchModel());
      this.fireDataEvent("NodeDoubleClicked", "root");
    });

    this.__desktop.add(this.__svgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__desktop.addListener("click", e => {
      this.__selectedItemChanged(null);
    }, this);

    this.__desktop.addListener("changeActiveWindow", e => {
      let winEmitting = e.getData();
      if (winEmitting && winEmitting.isActive() && winEmitting.classname.includes("workbench.Node")) {
        this.__selectedItemChanged(winEmitting.getNodeId());
      } else {
        this.__selectedItemChanged(null);
      }
    }, this);

    this.__nodesUI = [];
    this.__linksUI = [];

    let buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(BUTTON_SPACING));
    this.__desktopCanvas.add(buttonContainer, {
      bottom: 10,
      right: 10
    });
    // let addButton = this.__getPlusButton();
    // buttonContainer.add(addButton);
    // let removeButton = this.__getRemoveButton();
    // buttonContainer.add(removeButton);
    let unlinkButton = this.__unlinkButton = this.__getUnlinkButton();
    unlinkButton.setVisibility("excluded");
    buttonContainer.add(unlinkButton);

    this.addListener("dbltap", e => {
      // FIXME:
      const navBarHeight = 50;
      let x = e.getViewportLeft() - this.getBounds().left;
      let y = e.getViewportTop() - navBarHeight;
      const pos = {
        x: x,
        y: y
      };
      let srvCat = this.__createServicesCatalogue(pos);
      srvCat.open();
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "removeLink": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    }
  },

  members: {
    __unlinkButton: null,
    __nodesUI: null,
    __linksUI: null,
    __inputNodesLayout: null,
    __outputNodesLayout: null,
    __desktop: null,
    __svgWidget: null,
    __tempLinkNodeId: null,
    __tempLinkRepr: null,
    __pointerPosX: null,
    __pointerPosY: null,
    __selectedItemId: null,
    __currentModel: null,

    __getPlusButton: function() {
      const icon = "@FontAwesome5Solid/plus/32"; // qxapp.dev.Placeholders.getIcon("fa-plus", 32);
      let plusButton = new qx.ui.form.Button(null, icon);
      plusButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      plusButton.addListener("execute", function() {
        this.openServicesCatalogue();
      }, this);
      return plusButton;
    },

    __getRemoveButton: function() {
      const icon = "@FontAwesome5Solid/trash/32";
      let removeButton = new qx.ui.form.Button(null, icon);
      removeButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      removeButton.addListener("execute", function() {
        if (this.__selectedItemId && this.__isSelectedItemALink(this.__selectedItemId)) {
          this.__removeLink(this.__getLinkUI(this.__selectedItemId));
          this.__selectedItemId = null;
        } else {
          this.__removeSelectedNode();
        }
      }, this);
      return removeButton;
    },

    __getUnlinkButton: function() {
      const icon = "@FontAwesome5Solid/unlink/16";
      let unlinkBtn = new qx.ui.form.Button(null, icon);
      unlinkBtn.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      unlinkBtn.addListener("execute", function() {
        if (this.__selectedItemId && this.__isSelectedItemALink(this.__selectedItemId)) {
          this.__removeLink(this.__getLinkUI(this.__selectedItemId));
          this.__selectedItemId = null;
        }
      }, this);
      return unlinkBtn;
    },

    openServicesCatalogue: function() {
      let srvCat = this.__createServicesCatalogue();
      srvCat.open();
    },

    __createServicesCatalogue: function(pos) {
      let srvCat = new qxapp.component.workbench.servicesCatalogue.ServicesCatalogue();
      if (pos) {
        srvCat.moveTo(pos.x, pos.y);
      } else {
        // srvCat.center();
        const bounds = this.getLayoutParent().getBounds();
        const workbenchViewCenter = {
          x: bounds.left + parseInt((bounds.left + bounds.width) / 2),
          y: bounds.top + parseInt((bounds.top + bounds.height) / 2)
        };
        srvCat.moveTo(workbenchViewCenter.x - 200, workbenchViewCenter.y - 200);
      }
      srvCat.addListener("AddService", ev => {
        this.__addServiceFromCatalogue(ev, pos);
      }, this);
      return srvCat;
    },

    __addServiceFromCatalogue: function(e, pos) {
      const data = e.getData();
      const service = data.service;
      let nodeAId = data.contextNodeId;
      let portA = data.contextPort;

      let nodeModel = this.getWorkbenchModel().createNodeModel(service.getKey(), service.getVersion());
      let parent = null;
      if (this.__currentModel.isContainer()) {
        parent = this.__currentModel;
      }
      this.getWorkbenchModel().addNodeModel(nodeModel, parent);

      let nodeUI = this.__createNodeUI(nodeModel.getNodeId());
      this.__addNodeToWorkbench(nodeUI, pos);

      if (nodeAId !== null && portA !== null) {
        let nodeBId = nodeUI.getNodeId();
        let portB = this.__findCompatiblePort(nodeUI, portA);
        // swap node-ports to have node1 as input and node2 as output
        if (portA.isInput) {
          [nodeAId, portA, nodeBId, portB] = [nodeBId, portB, nodeAId, portA];
        }
        this.__createLinkBetweenNodes({
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
      nodeUI.getNodeModel().setPosition(position.x, position.y);
      nodeUI.moveTo(position.x, position.y);
      this.addWindowToDesktop(nodeUI);
      this.__nodesUI.push(nodeUI);

      nodeUI.addListener("NodeMoving", function() {
        this.__updateLinks(nodeUI);
        this.__updatePosition(nodeUI);
      }, this);

      nodeUI.addListener("appear", function() {
        this.__updateLinks(nodeUI);
      }, this);

      nodeUI.addListener("dbltap", e => {
        this.fireDataEvent("NodeDoubleClicked", nodeUI.getNodeId());
        e.stopPropagation();
      }, this);

      // qx.ui.core.queue.Widget.flush();
      qx.ui.core.queue.Layout.flush();
    },

    __createNodeUI: function(nodeId) {
      let nodeModel = this.getWorkbenchModel().getNodeModel(nodeId);

      let nodeBase = new qxapp.component.workbench.NodeBase(nodeModel);
      nodeBase.createNodeLayout();
      nodeBase.populateNodeLayout();
      this.__createDragDropMechanism(nodeBase);
      return nodeBase;
    },

    __createLinkUI: function(node1Id, node2Id, linkId) {
      let linkModel = this.getWorkbenchModel().createLinkModel(linkId, node1Id, node2Id);
      this.getWorkbenchModel().addLinkModel(linkModel);

      // build representation
      let node1 = this.getNodeUI(node1Id);
      let node2 = this.getNodeUI(node2Id);
      if (this.__currentModel.isContainer() && node2.getNodeId() === this.__currentModel.getNodeId()) {
        node1.getNodeModel().setIsOutputNode(true);
      } else {
        node2.getNodeModel().addInputNode(node1Id);
      }
      let port1 = node1.getOutputPort();
      let port2 = node2.getInputPort();
      const pointList = this.__getLinkPoints(node1, port1, node2, port2);
      const x1 = pointList[0] ? pointList[0][0] : 0;
      const y1 = pointList[0] ? pointList[0][1] : 0;
      const x2 = pointList[1] ? pointList[1][0] : 0;
      const y2 = pointList[1] ? pointList[1][1] : 0;
      let linkRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);

      let link = new qxapp.component.workbench.LinkBase(linkModel, linkRepresentation);
      this.__linksUI.push(link);

      link.getRepresentation().node.addEventListener("click", e => {
        // this is needed to get out of the context of svg
        link.fireDataEvent("linkSelected", link.getLinkId());
        e.stopPropagation();
      }, this);

      link.addListener("linkSelected", e => {
        this.__selectedItemChanged(link.getLinkId());
      }, this);

      return link;
    },

    __createDragDropMechanism: function(nodeBase) {
      const evType = "pointermove";
      nodeBase.addListener("LinkDragStart", e => {
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

        this.__tempLinkNodeId = dragData.dragNodeId;
        this.__tempLinkIsInput = dragData.dragIsInput;
        qx.bom.Element.addListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);

      nodeBase.addListener("LinkDragOver", e => {
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

      nodeBase.addListener("LinkDrop", e => {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        if (event.supportsType("osparc-node-link")) {
          let dragNodeId = event.getData("osparc-node-link").dragNodeId;
          let dragIsInput = event.getData("osparc-node-link").dragIsInput;

          let nodeAId = dropIsInput ? dragNodeId : dropNodeId;
          let nodeBId = dragIsInput ? dragNodeId : dropNodeId;

          this.__createLinkBetweenNodes({
            nodeUuid: nodeAId
          }, {
            nodeUuid: nodeBId
          });
          this.__removeTempLink();
          qx.bom.Element.removeListener(
            this.__desktop,
            evType,
            this.__startTempLink,
            this
          );
        }
      }, this);

      nodeBase.addListener("LinkDragEnd", e => {
        let data = e.getData();
        let dragNodeId = data.nodeId;

        let posX = this.__pointerPosX;
        let posY = this.__pointerPosY;
        if (this.__tempLinkNodeId === dragNodeId) {
          const pos = {
            x: posX,
            y: posY
          };
          let srvCat = this.__createServicesCatalogue(pos);
          if (this.__tempLinkIsInput === true) {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getInputPort());
          } else {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getOutputPort());
          }
          srvCat.addListener("close", function(ev) {
            this.__removeTempLink();
          }, this);
          srvCat.open();
        }
        qx.bom.Element.removeListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);
    },

    __createInputNodeUI: function(inputNodeModel) {
      let nodeInput = new qxapp.component.widget.NodeInput(inputNodeModel);
      nodeInput.populateNodeLayout();
      this.__createDragDropMechanism(nodeInput);
      this.__inputNodesLayout.add(nodeInput, {
        flex: 1
      });
      return nodeInput;
    },

    __createInputNodeUIs: function(model) {
      const inputNodes = model.getInputNodes();
      for (let i = 0; i < inputNodes.length; i++) {
        let inputNodeModel = this.getWorkbenchModel().getNodeModel(inputNodes[i]);
        let inputLabel = this.__createInputNodeUI(inputNodeModel);
        this.__nodesUI.push(inputLabel);
      }
    },

    __clearInputNodeUIs: function() {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length - 1);
      }
    },

    __createNodeExposedUI: function(currentModel) {
      let nodeOutput = new qxapp.component.widget.NodeExposed(currentModel);
      nodeOutput.populateNodeLayout();
      this.__createDragDropMechanism(nodeOutput);
      this.__outputNodesLayout.add(nodeOutput, {
        flex: 1
      });
      return nodeOutput;
    },

    __createNodeExposedUIs: function(model) {
      let outputLabel = this.__createNodeExposedUI(model);
      this.__nodesUI.push(outputLabel);
    },

    __clearNodeExposedUIs: function() {
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
      return qxapp.data.Store.getInstance().areNodesCompatible(topLevelPort1, topLevelPort2);
    },

    __findCompatiblePort: function(nodeB, portA) {
      if (portA.isInput && nodeB.getOutputPort()) {
        return nodeB.getOutputPort();
      } else if (nodeB.getInputPort()) {
        return nodeB.getInputPort();
      }
      return null;
    },

    __createLinkBetweenNodes: function(from, to, linkId) {
      let node1Id = from.nodeUuid;
      let node2Id = to.nodeUuid;
      this.__createLinkUI(node1Id, node2Id, linkId);
    },

    __createLinkBetweenNodesAndInputNodes: function(from, to, linkId) {
      const inputNodes = this.__inputNodesLayout.getChildren();
      // Children[0] is the title
      for (let i = 1; i < inputNodes.length; i++) {
        const inputNodeId = inputNodes[i].getNodeId();
        if (inputNodeId === from.nodeUuid) {
          let node1Id = from.nodeUuid;
          let node2Id = to.nodeUuid;
          this.__createLinkUI(node1Id, node2Id, linkId);
        }
      }
    },

    __createLinkToExposedOutputs: function(from, to, linkId) {
      let node1Id = from.nodeUuid;
      let node2Id = to.nodeUuid;
      this.__createLinkUI(node1Id, node2Id, linkId);
    },

    __updatePosition: function(node) {
      const cBounds = node.getCurrentBounds();
      let nodeModel = this.getWorkbenchModel().getNodeModel(node.getNodeId());
      nodeModel.setPosition(cBounds.left, cBounds.top);
    },

    __updateLinks: function(node) {
      let linksInvolved = this.getWorkbenchModel().getConnectedLinks(node.getNodeId());

      linksInvolved.forEach(linkId => {
        let link = this.__getLinkUI(linkId);
        if (link) {
          let node1 = this.getNodeUI(link.getLinkModel().getInputNodeId());
          let port1 = node1.getOutputPort();
          let node2 = this.getNodeUI(link.getLinkModel().getOutputNodeId());
          let port2 = node2.getInputPort();
          const pointList = this.__getLinkPoints(node1, port1, node2, port2);
          const x1 = pointList[0][0];
          const y1 = pointList[0][1];
          const x2 = pointList[1][0];
          const y2 = pointList[1][1];
          this.__svgWidget.updateCurve(link.getRepresentation(), x1, y1, x2, y2);
        }
      });
    },

    __startTempLink: function(pointerEvent) {
      if (this.__tempLinkNodeId === null) {
        return;
      }
      let node = this.getNodeUI(this.__tempLinkNodeId);
      if (node === null) {
        return;
      }
      let port;
      if (this.__tempLinkIsInput) {
        port = node.getInputPort();
      } else {
        port = node.getOutputPort();
      }
      if (port === null) {
        return;
      }

      let x1;
      let y1;
      let x2;
      let y2;
      const portPos = node.getLinkPoint(port);
      // FIXME:
      const navBarHeight = 50;
      const inputNodesLayoutWidth = this.__inputNodesLayout.isVisible() ? this.__inputNodesLayout.getWidth() : 0;
      this.__pointerPosX = pointerEvent.getViewportLeft() - this.getBounds().left - inputNodesLayoutWidth;
      this.__pointerPosY = pointerEvent.getViewportTop() - navBarHeight;

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

      if (this.__tempLinkRepr === null) {
        this.__tempLinkRepr = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      } else {
        this.__svgWidget.updateCurve(this.__tempLinkRepr, x1, y1, x2, y2);
      }
    },

    __removeTempLink: function() {
      if (this.__tempLinkRepr !== null) {
        this.__svgWidget.removeCurve(this.__tempLinkRepr);
      }
      this.__tempLinkRepr = null;
      this.__tempLinkNodeId = null;
      this.__pointerPosX = null;
      this.__pointerPosY = null;
    },

    __getLinkPoints: function(node1, port1, node2, port2) {
      let p1 = null;
      let p2 = null;
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }
      p1 = node1.getLinkPoint(port1);
      if (this.__currentModel.isContainer() && node2.getNodeModel().getNodeId() === this.__currentModel.getNodeId()) {
        // connection to the exposed output
        const dc = this.__desktopCanvas.getBounds();
        const onl = this.__outputNodesLayout.getBounds();
        p2 = [
          parseInt(dc.width - 6),
          parseInt(onl.height / 2)
        ];
      } else {
        p2 = node2.getLinkPoint(port2);
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

    __getLinkUI: function(linkId) {
      for (let i = 0; i < this.__linksUI.length; i++) {
        if (this.__linksUI[i].getLinkId() === linkId) {
          return this.__linksUI[i];
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

    clearLink(linkId) {
      this.__clearLink(this.__getLinkUI(linkId));
    },

    __removeLink: function(link) {
      this.fireDataEvent("removeLink", link.getLinkId());
    },

    __removeAllLinks: function() {
      while (this.__linksUI.length > 0) {
        this.__removeLink(this.__linksUI[this.__linksUI.length - 1]);
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    __clearNode: function(nodeId) {
      let node = this.getNodeUI(nodeId);
      if (this.__desktop.getChildren().includes(node)) {
        this.__desktop.remove(node);
      }
      let index = this.__nodesUI.indexOf(node);
      if (index > -1) {
        this.__nodesUI.splice(index, 1);
      }
    },

    __clearAllNodes: function() {
      while (this.__nodesUI.length > 0) {
        this.__clearNode(this.__nodesUI[this.__nodesUI.length - 1].getNodeId());
      }
    },

    __clearLink: function(link) {
      this.__svgWidget.removeCurve(link.getRepresentation());
      let index = this.__linksUI.indexOf(link);
      if (index > -1) {
        this.__linksUI.splice(index, 1);
      }
    },

    __clearAllLinks: function() {
      while (this.__linksUI.length > 0) {
        this.__clearLink(this.__linksUI[this.__linksUI.length - 1]);
      }
    },

    clearAll: function() {
      this.__clearAllNodes();
      this.__clearAllLinks();
    },

    loadModel: function(model) {
      this.clearAll();

      this.__currentModel = model;

      if (model) {
        const isContainer = model.isContainer();
        if (isContainer) {
          this.__inputNodesLayout.setVisibility("visible");
          this.__clearInputNodeUIs();
          this.__createInputNodeUIs(model);
          this.__outputNodesLayout.setVisibility("visible");
          this.__clearNodeExposedUIs();
          this.__createNodeExposedUIs(model);
        } else {
          this.__inputNodesLayout.setVisibility("excluded");
          this.__outputNodesLayout.setVisibility("excluded");
        }
        qx.ui.core.queue.Visibility.flush();

        let nodes = isContainer ? model.getInnerNodes() : model.getNodeModels();
        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          let nodeUI = this.__createNodeUI(nodeUuid);
          this.__addNodeToWorkbench(nodeUI, nodeModel.getPosition());
        }

        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          const inputNodes = nodeModel.getInputNodes();
          for (let i = 0; i < inputNodes.length; i++) {
            let inputNode = inputNodes[i];
            if (inputNode in nodes) {
              this.__createLinkBetweenNodes({
                nodeUuid: inputNode
              }, {
                nodeUuid: nodeUuid
              });
            } else {
              if (!isContainer) {
                console.log("Shouldn't be the case");
              }
              this.__createLinkBetweenNodesAndInputNodes({
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
            this.__createLinkToExposedOutputs({
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

      // qx.ui.core.queue.Widget.flush();
    },

    clearProgressData: function() {
      for (let i = 0; i < this.__nodesUI.length; i++) {
        this.__nodesUI[i].setProgress(0);
      }
    },

    updateProgress: function(nodeId, progress) {
      let node = this.getNodeUI(nodeId);
      if (node) {
        node.setProgress(progress);
      }
    },

    __selectedItemChanged: function(newID) {
      if (newID === this.__selectedItemId) {
        return;
      }

      let oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemALink(oldId)) {
          let unselectedLink = this.__getLinkUI(oldId);
          const unselectedColor = qxapp.theme.Color.colors["workbench-link-comp-active"];
          this.__svgWidget.updateColor(unselectedLink.getRepresentation(), unselectedColor);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemALink(newID)) {
        let selectedLink = this.__getLinkUI(newID);
        const selectedColor = qxapp.theme.Color.colors["workbench-link-selected"];
        this.__svgWidget.updateColor(selectedLink.getRepresentation(), selectedColor);
      }

      this.__unlinkButton.setVisibility(this.__isSelectedItemALink(newID) ? "visible" : "excluded");
    },

    __isSelectedItemALink: function() {
      return Boolean(this.__getLinkUI(this.__selectedItemId));
    }
  }
});
