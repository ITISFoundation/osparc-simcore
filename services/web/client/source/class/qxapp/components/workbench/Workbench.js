/* eslint no-warning-comments: "off" */
/* global window */

const BUTTON_SIZE = 50;
const BUTTON_SPACING = 10;
const INPUTS_WIDTH = 200;

qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function(workbenchModel) {
    this.base();

    let hBox = new qx.ui.layout.HBox();
    this.set({
      layout: hBox
    });

    let inputNodesLayout = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    inputNodesLayout.set({
      width: INPUTS_WIDTH,
      maxWidth: INPUTS_WIDTH,
      // backgroundColor: "blue",
      allowGrowX: false
    });
    this.add(inputNodesLayout);
    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label("Inputs").set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);

    this.__desktopCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    this.add(this.__desktopCanvas, {
      flex : 1
    });

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.__desktopCanvas.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.setWorkbenchModel(workbenchModel);
    this.__svgWidget = new qxapp.components.workbench.SvgWidget("SvgWidgetLayer");
    // this gets fired once the widget has appeared and the library has been loaded
    // due to the qx rendering, this will always happen after setup, so we are
    // sure to catch this event
    this.__svgWidget.addListenerOnce("SvgWidgetReady", () => {
      // Will be called only the first time Svg lib is loaded
      this.__loadProject();
    });

    this.__desktop.add(this.__svgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__desktop.addListener("click", function(e) {
      this.__selectedItemChanged(null);
    }, this);

    this.__desktop.addListener("changeActiveWindow", function(e) {
      let winEmitting = e.getData();
      if (winEmitting && winEmitting.isActive() && winEmitting.classname.includes("workbench.Node")) {
        this.__selectedItemChanged(winEmitting.getNodeId());
      } else {
        this.__selectedItemChanged(null);
      }
    }, this);
    // TODO how about making the LoggerView a singleton then it could be accessed from anywhere
    this.__logger = new qxapp.components.workbench.logger.LoggerView();
    this.__desktop.add(this.__logger);

    this.__nodesUI = [];
    this.__linksUI = [];

    let buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(BUTTON_SPACING));
    this.__desktopCanvas.add(buttonContainer, {
      bottom: 10,
      right: 10
    });
    [
      this.__getPlusButton(),
      this.__getRemoveButton()
    ].forEach(widget => {
      buttonContainer.add(widget);
    });

    this.addListener("dblclick", function(pointerEvent) {
      // FIXME:
      const navBarHeight = 50;
      let x = pointerEvent.getViewportLeft() - this.getBounds().left;
      let y = pointerEvent.getViewportTop() - navBarHeight;

      let srvCat = new qxapp.components.workbench.servicesCatalogue.ServicesCatalogue();
      srvCat.moveTo(x, y);
      srvCat.open();
      let pos = {
        x: x,
        y: y
      };
      srvCat.addListener("AddService", function(e) {
        this.__addServiceFromCatalogue(e, pos);
      }, this);
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    }
  },

  members: {
    __nodesUI: null,
    __linksUI: null,
    __inputNodesLayout: null,
    __desktop: null,
    __svgWidget: null,
    __logger: null,
    __tempLinkNodeId: null,
    __tempLinkPortId: null,
    __tempLinkRepr: null,
    __pointerPosX: null,
    __pointerPosY: null,
    __selectedItemId: null,
    __playButton: null,
    __stopButton: null,

    getLogger: function() {
      return this.__logger;
    },

    showLogger: function() {
      if (this.__logger.isVisible()) {
        this.__logger.close();
      } else {
        const dHeight = this.__desktop.getBounds().height;
        const lHeight = this.__logger.getHeight();
        this.__logger.moveTo(10, dHeight-lHeight-10);
        this.__logger.open();
      }
    },

    __getPlusButton: function() {
      const icon = "@FontAwesome5Solid/plus/32"; // qxapp.dev.Placeholders.getIcon("fa-plus", 32);
      let plusButton = new qx.ui.form.Button(null, icon);
      plusButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      plusButton.addListener("execute", function() {
        let srvCat = new qxapp.components.workbench.servicesCatalogue.ServicesCatalogue();
        srvCat.moveTo(200, 200);
        srvCat.open();
        srvCat.addListener("AddService", function(e) {
          this.__addServiceFromCatalogue(e);
        }, this);
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
          this.__removeLink(this.__getLink(this.__selectedItemId));
          this.__selectedItemId = null;
        } else {
          this.__removeSelectedNode();
        }
      }, this);
      return removeButton;
    },

    __addServiceFromCatalogue: function(e, pos) {
      let data = e.getData();
      let metaData = data.service;
      let nodeAId = data.contextNodeId;
      let portA = data.contextPort;

      let nodeB = this.__createNode(metaData);
      this.__addNodeToWorkbench(nodeB, pos);

      if (nodeAId !== null && portA !== null) {
        let nodeBId = nodeB.getNodeId();
        let portB = this.__findCompatiblePort(nodeB, portA);
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

    __addNodeToWorkbench: function(node, position) {
      if (position === undefined || position === null) {
        position = {};
        let farthestRight = 0;
        for (let i=0; i < this.__nodesUI.length; i++) {
          let boundPos = this.__nodesUI[i].getBounds();
          let rightPos = boundPos.left + boundPos.width;
          if (farthestRight < rightPos) {
            farthestRight = rightPos;
          }
        }
        position.x = 50 + farthestRight;
        position.y = 200;
      }
      node.getNodeModel().setPosition(position.x, position.y);
      node.moveTo(position.x, position.y);
      this.addWindowToDesktop(node);
      this.__nodesUI.push(node);

      node.addListener("NodeMoving", function() {
        this.__updateLinks(node);
      }, this);

      node.addListener("appear", function() {
        this.__updateLinks(node);
      }, this);

      node.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", node.getNodeId());
        e.stopPropagation();
      }, this);

      qx.ui.core.queue.Layout.flush();
    },

    __createNode: function(metaData, uuid, nodeData) {
      let nodeModel = this.getWorkbenchModel().createNode(metaData, uuid, nodeData);

      let nodeBase = new qxapp.components.workbench.NodeBase(nodeModel);
      nodeBase.createNodeLayout();
      nodeBase.populateNodeLayout();

      const evType = "pointermove";
      nodeBase.addListener("LinkDragStart", function(e) {
        let data = e.getData();
        let event = data.event;
        let dragNodeId = data.nodeId;
        let dragIsInput = data.isInput;
        let dragPortId = data.portId;

        // Register supported actions
        event.addAction("move");

        // Register supported types
        event.addType("osparc-metaData");
        let dragData = {
          dragNodeId: dragNodeId,
          dragIsInput: dragIsInput,
          dragPortId: dragPortId
        };
        event.addData("osparc-metaData", dragData);

        this.__tempLinkNodeId = dragData.dragNodeId;
        this.__tempLinkIsInput = dragData.dragIsInput;
        this.__tempLinkPortId = dragData.dragPortId;
        qx.bom.Element.addListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);

      nodeBase.addListener("LinkDragOver", function(e) {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;
        let dropPortId = data.portId;

        let compatible = false;
        if (event.supportsType("osparc-metaData")) {
          const dragNodeId = event.getData("osparc-metaData").dragNodeId;
          const dragIsInput = event.getData("osparc-metaData").dragIsInput;
          const dragPortId = event.getData("osparc-metaData").dragPortId;
          const dragNode = this.getNodeUI(dragNodeId);
          const dropNode = this.getNodeUI(dropNodeId);
          const dragPortTarget = dragIsInput ? dragNode.getInputPort(dragPortId) : dragNode.getOutputPort(dragPortId);
          const dropPortTarget = dropIsInput ? dropNode.getInputPort(dropPortId) : dropNode.getOutputPort(dropPortId);
          compatible = this.__arePortsCompatible(dragPortTarget, dropPortTarget);
        }

        if (!compatible) {
          event.preventDefault();
        }
      }, this);

      nodeBase.addListener("LinkDrop", function(e) {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        if (event.supportsType("osparc-metaData")) {
          let dragNodeId = event.getData("osparc-metaData").dragNodeId;
          let dragIsInput = event.getData("osparc-metaData").dragIsInput;

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

      nodeBase.addListener("LinkDragEnd", function(e) {
        let data = e.getData();
        let dragNodeId = data.nodeId;
        let dragPortId = data.portId;

        let posX = this.__pointerPosX;
        let posY = this.__pointerPosY;
        if (this.__tempLinkNodeId === dragNodeId && this.__tempLinkPortId === dragPortId) {
          let srvCat = new qxapp.components.workbench.servicesCatalogue.ServicesCatalogue();
          if (this.__tempLinkIsInput === true) {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getInputPort());
          } else {
            srvCat.setContext(dragNodeId, this.getNodeUI(dragNodeId).getOutputPort());
          }
          srvCat.moveTo(posX, posY);
          srvCat.open();
          let pos = {
            x: posX,
            y: posY
          };
          srvCat.addListener("AddService", function(ev) {
            this.__addServiceFromCatalogue(ev, pos);
          }, this);
          srvCat.addListener("close", function(ev) {
            this.__removeTempLink();
          }, this);
        }
        qx.bom.Element.removeListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);

      return nodeBase;
    },

    __removeSelectedNode: function() {
      for (let i=0; i<this.__nodesUI.length; i++) {
        if (this.__desktop.getActiveWindow() === this.__nodesUI[i]) {
          let connectedLinks = this.__getConnectedLinks(this.__nodesUI[i].getNodeId());
          for (let j=0; j<connectedLinks.length; j++) {
            this.__removeLink(this.__getLink(connectedLinks[j]));
          }
          this.__removeNode(this.__nodesUI[i]);
          return;
        }
      }
    },

    __arePortsCompatible: function(port1, port2) {
      return qxapp.data.Store.getInstance().arePortsCompatible(port1, port2);
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

      let node1 = this.getNodeUI(node1Id);
      let port1 = node1.getOutputPort();
      let node2 = this.getNodeUI(node2Id);
      let port2 = node2.getInputPort();

      node2.getNodeModel().addInputNode(node1Id);
      linkId = linkId || qxapp.utils.Utils.uuidv4();

      const pointList = this.__getLinkPoints(node1, port1, node2, port2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);

      let link = new qxapp.components.workbench.LinkBase(linkRepresentation);
      link.setInputNodeId(node1.getNodeId());
      link.setOutputNodeId(node2.getNodeId());
      link.setLinkId(linkId);
      this.__linksUI.push(link);

      link.getRepresentation().node.addEventListener("click", function(e) {
        // this is needed to get out of the context of svg
        link.fireDataEvent("linkSelected", link.getLinkId());
        e.stopPropagation();
      }, this);

      link.addListener("linkSelected", function(e) {
        this.__selectedItemChanged(link.getLinkId());
      }, this);

      return link;
    },

    __updateLinks: function(node) {
      let linksInvolved = this.__getConnectedLinks(node.getNodeId());

      linksInvolved.forEach(linkId => {
        let link = this.__getLink(linkId);
        if (link) {
          let node1 = this.getNodeUI(link.getInputNodeId());
          let port1 = node1.getOutputPort();
          let node2 = this.getNodeUI(link.getOutputNodeId());
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
      if (this.__tempLinkNodeId === null || this.__tempLinkPortId === null) {
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
      this.__tempLinkPortId = null;
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
      p2 = node2.getLinkPoint(port2);
      // hack to place the arrow-head properly
      p2[0] -= 6;
      return [p1, p2];
    },

    getNodeUI: function(id) {
      for (let i = 0; i < this.__nodesUI.length; i++) {
        if (this.__nodesUI[i].getNodeId() === id) {
          return this.__nodesUI[i];
        }
      }
      return null;
    },

    __getConnectedLinks: function(nodeId) {
      let connectedLinks = [];
      for (let i = 0; i < this.__linksUI.length; i++) {
        if (this.__linksUI[i].getInputNodeId() === nodeId) {
          connectedLinks.push(this.__linksUI[i].getLinkId());
        }
        if (this.__linksUI[i].getOutputNodeId() === nodeId) {
          connectedLinks.push(this.__linksUI[i].getLinkId());
        }
      }
      return connectedLinks;
    },

    __getLink: function(id) {
      for (let i = 0; i < this.__linksUI.length; i++) {
        if (this.__linksUI[i].getLinkId() === id) {
          return this.__linksUI[i];
        }
      }
      return null;
    },

    __removeNode: function(node) {
      const removed = this.getWorkbenchModel().removeNode(node.getNodeModel());
      if (removed) {
        this.__clearNode(node);
      }
    },

    __removeAllNodes: function() {
      while (this.__nodesUI.length > 0) {
        this.__removeNode(this.__nodesUI[this.__nodesUI.length-1]);
      }
    },

    __removeLink: function(link) {
      const removed = this.getWorkbenchModel().removeLink(link.getInputNodeId(), link.getOutputNodeId());
      if (removed) {
        this.__clearLink(link);
      }
    },

    __removeAllLinks: function() {
      while (this.__linksUI.length > 0) {
        this.__removeLink(this.__linksUI[this.__linksUI.length-1]);
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    __clearNode: function(node) {
      this.__desktop.remove(node);
      let index = this.__nodesUI.indexOf(node);
      if (index > -1) {
        this.__nodesUI.splice(index, 1);
      }
    },

    __clearAllNodes: function() {
      while (this.__nodesUI.length > 0) {
        this.__clearNode(this.__nodesUI[this.__nodesUI.length-1]);
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
        this.__clearLink(this.__linksUI[this.__linksUI.length-1]);
      }
    },

    clearAll: function() {
      this.__clearAllNodes();
      this.__clearAllLinks();
    },

    __loadProject: function() {
      this.removeAll();

      const workbenchModel = this.getWorkbenchModel();
      this.loadRoot(workbenchModel);
    },

    loadRoot: function(model) {
      this.clearAll();

      if (model) {
        this.__inputNodesLayout.setVisibility("excluded");

        let nodes = model.getNodes();
        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          const metaData = nodeModel.getMetaData();
          let node = this.__createNode(metaData, nodeUuid, nodeModel);
          this.__addNodeToWorkbench(node, nodeModel.getPosition());
        }

        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          const inputNodes = nodeModel.getInputNodes();
          for (let i=0; i<inputNodes.length; i++) {
            this.__createLinkBetweenNodes({
              nodeUuid: inputNodes[i]
            }, {
              nodeUuid: nodeUuid
            });
          }
        }
      }
    },

    loadContainer: function(model) {
      this.clearAll();

      if (model) {
        this.__addInputNodes(model);

        let nodes = model.getInnerNodes();
        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          const metaData = nodeModel.getMetaData();
          let node = this.__createNode(metaData, nodeUuid, nodeModel);
          this.__addNodeToWorkbench(node, nodeModel.getPosition());
        }

        for (const nodeUuid in nodes) {
          const nodeModel = nodes[nodeUuid];
          const inputNodes = nodeModel.getInputNodes();
          for (let i=0; i<inputNodes.length; i++) {
            let inputNode = inputNodes[i];
            if (inputNode in nodes) {
              this.__createLinkBetweenNodes({
                nodeUuid: inputNode
              }, {
                nodeUuid: nodeUuid
              });
            }
          }
        }
      }
    },

    __addInputNodes: function(model) {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length-1);
      }

      const inputNodes = model.getInputNodes();
      this.__inputNodesLayout.setVisibility("visible");
      for (let i=0; i<inputNodes.length; i++) {
        let inputNode = this.getWorkbenchModel().getNodeModel(inputNodes[i]);
        const nodeName = inputNode.getName();
        let inputLabel = new qx.ui.basic.Atom(nodeName).set({
          center : true,
          draggable: true,
          droppable: true,
          decorator: "main"
        });
        inputLabel.nodeId = inputNode.getNodeId();

        this.__inputNodesLayout.add(inputLabel, {
          flex: 1
        });
      }
    },

    saveProject: function() {
      const savePosition = true;
      this.serializePipeline(savePosition);
    },

    serializePipeline: function(savePosition = false) {
      let workbench = this.getWorkbenchModel().serializeWorkbench(savePosition);
      return workbench;
    },

    addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();

      qx.ui.core.queue.Layout.flush();
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
          let unselectedLink = this.__getLink(oldId);
          const unselectedColor = qxapp.theme.Color.colors["workbench-link-comp-active"];
          this.__svgWidget.updateColor(unselectedLink.getRepresentation(), unselectedColor);
        }
      }

      this.__selectedItemId = newID;
      if (this.__isSelectedItemALink(newID)) {
        let selectedLink = this.__getLink(newID);
        const selectedColor = qxapp.theme.Color.colors["workbench-link-selected"];
        this.__svgWidget.updateColor(selectedLink.getRepresentation(), selectedColor);
      }
    },

    __isSelectedItemALink: function() {
      return Boolean(this.__getLink(this.__selectedItemId));
    }
  }
});
