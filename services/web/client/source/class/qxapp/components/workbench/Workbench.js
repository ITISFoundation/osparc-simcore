/* eslint no-warning-comments: "off" */
/* global window */

const BUTTON_SIZE = 50;
const BUTTON_SPACING = 10;

qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function(workbenchData) {
    this.base();

    let canvas = new qx.ui.layout.Canvas();
    this.set({
      layout: canvas
    });

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__workbenchData = workbenchData;
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

    this.__nodes = [];
    this.__links = [];

    let buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(BUTTON_SPACING));
    this.add(buttonContainer, {
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

  members: {
    __workbenchData: null,
    __nodes: null,
    __links: null,
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
      const nodeImageId = metaData.key + "-" + metaData.version;
      let nodeAId = data.contextNodeId;
      let portA = data.contextPort;

      let nodeB = this.__createNode(nodeImageId, null);
      this.__addNodeToWorkbench(nodeB, pos);
      this.__nodes.push(nodeB);

      if (nodeAId !== null && portA !== null) {
        let nodeBId = nodeB.getNodeId();
        let portB = this.__findCompatiblePort(nodeB, portA);
        // swap node-ports to have node1 as input and node2 as output
        if (portA.isInput) {
          [nodeAId, portA, nodeBId, portB] = [nodeBId, portB, nodeAId, portA];
        }
        this.__addLink({
          nodeUuid: nodeAId,
          output: portA.portId
        }, {
          nodeUuid: nodeBId,
          input: portB.portId
        });
      }
    },

    __addNodeToWorkbench: function(node, position) {
      if (position === undefined || position === null) {
        let farthestRight = 0;
        for (let i=0; i < this.__nodes.length; i++) {
          let boundPos = this.__nodes[i].getBounds();
          let rightPos = boundPos.left + boundPos.width;
          if (farthestRight < rightPos) {
            farthestRight = rightPos;
          }
        }
        node.moveTo(50 + farthestRight, 200);
      } else {
        node.moveTo(position.x, position.y);
      }
      this.addWindowToDesktop(node);

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

    __createNode: function(nodeImageId, uuid, nodeData) {
      let nodeBase = new qxapp.components.workbench.NodeBase(nodeImageId, uuid);
      nodeBase.createNodeLayout();
      nodeBase.populateNodeLayout();
      nodeBase.populateNodeData(nodeData);
      let store = qxapp.data.Store.getInstance();
      let metaData = store.getNodeMetaData(nodeImageId);
      if (metaData.type === "container") {
        let innerNodes = nodeBase.createInnerNodes(metaData.innerServices);
        this.__nodes = this.__nodes.concat(innerNodes);
      }

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
          const dragNode = this.getNode(dragNodeId);
          const dropNode = this.getNode(dropNodeId);
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
        let dropPortId = data.portId;

        if (event.supportsType("osparc-metaData")) {
          let dragNodeId = event.getData("osparc-metaData").dragNodeId;
          let dragIsInput = event.getData("osparc-metaData").dragIsInput;
          let dragPortId = event.getData("osparc-metaData").dragPortId;

          let nodeAId = dropIsInput ? dragNodeId : dropNodeId;
          let nodeAPortId = dropIsInput ? dragPortId : dropPortId;
          let nodeBId = dragIsInput ? dragNodeId : dropNodeId;
          let nodeBPortId = dragIsInput ? dragPortId : dropPortId;

          this.__addLink({
            nodeUuid: nodeAId,
            output: nodeAPortId
          }, {
            nodeUuid: nodeBId,
            input: nodeBPortId
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
        // let event = data.event"];
        let dragNodeId = data.nodeId;
        let dragPortId = data.portId;

        let posX = this.__pointerPosX;
        let posY = this.__pointerPosY;
        if (this.__tempLinkNodeId === dragNodeId && this.__tempLinkPortId === dragPortId) {
          let srvCat = new qxapp.components.workbench.servicesCatalogue.ServicesCatalogue();
          if (this.__tempLinkIsInput === true) {
            srvCat.setContext(dragNodeId, this.getNode(dragNodeId).getInputPort(dragPortId));
          } else {
            srvCat.setContext(dragNodeId, this.getNode(dragNodeId).getOutputPort(dragPortId));
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
      for (let i=0; i<this.__nodes.length; i++) {
        if (this.__desktop.getActiveWindow() === this.__nodes[i]) {
          let connectedLinks = this.__getConnectedLinks(this.__nodes[i].getNodeId());
          for (let j=0; j<connectedLinks.length; j++) {
            this.__removeLink(this.__getLink(connectedLinks[j]));
          }
          this.__removeNode(this.__nodes[i]);
          return;
        }
      }
    },

    __getMimeType: function(type) {
      let match = type.match(/^data:([^/\s]+\/[^/;\s])/);
      if (match) {
        return match[1];
      }
      return null;
    },

    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = this.__getMimeType(typeA);
      let mtB = this.__getMimeType(typeB);
      return mtA && mtB &&
        new qxapp.data.MimeType(mtA).match(new qxapp.data.MimeType(mtB));
    },

    __arePortsCompatible: function(port1, port2) {
      return this.__matchPortType(port1.portType, port2.portType) &&
        (port1.isInput !== port2.isInput);
    },

    __findCompatiblePort: function(nodeB, portA) {
      if (portA.isInput) {
        for (let portBId in nodeB.getOutputPorts()) {
          let portB = nodeB.getOutputPort(portBId);
          if (this.__matchPortType(portA.portType, portB.portType)) {
            return portB;
          }
        }
      } else {
        for (let portBId in nodeB.getInputPorts()) {
          let portB = nodeB.getInputPort(portBId);
          if (this.__matchPortType(portA.portType, portB.portType)) {
            return portB;
          }
        }
      }
      return null;
    },

    __addLink: function(from, to, linkId) {
      let node1Id = from.nodeUuid;
      let port1Id = from.output;
      let node2Id = to.nodeUuid;
      let port2Id = to.input;

      let node1 = this.getNode(node1Id);
      let port1 = node1.getOutputPort(port1Id);
      let node2 = this.getNode(node2Id);
      let port2 = node2.getInputPort(port2Id);

      const pointList = this.__getLinkPoints(node1, port1, node2, port2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      let link = new qxapp.components.workbench.LinkBase(linkRepresentation);
      link.setInputNodeId(node1.getNodeId());
      link.setInputPortId(port1.portId);
      link.setOutputNodeId(node2.getNodeId());
      link.setOutputPortId(port2.portId);
      if (linkId !== undefined) {
        link.setLinkId(linkId);
      }
      this.__links.push(link);

      node2.getPropsWidget().enableProp(port2.portId, false);

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
          let node1 = this.getNode(link.getInputNodeId());
          let port1 = node1.getOutputPort(link.getInputPortId());
          let node2 = this.getNode(link.getOutputNodeId());
          let port2 = node2.getInputPort(link.getOutputPortId());
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
      let node = this.getNode(this.__tempLinkNodeId);
      if (node === null) {
        return;
      }
      let port;
      if (this.__tempLinkIsInput) {
        port = node.getInputPort(this.__tempLinkPortId);
      } else {
        port = node.getOutputPort(this.__tempLinkPortId);
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
      this.__pointerPosX = pointerEvent.getViewportLeft() - this.getBounds().left;
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

    getNode: function(id) {
      for (let i = 0; i < this.__nodes.length; i++) {
        if (this.__nodes[i].getNodeId() === id) {
          return this.__nodes[i];
        }
      }
      return null;
    },

    __getConnectedLinks: function(nodeId) {
      let connectedLinks = [];
      for (let i = 0; i < this.__links.length; i++) {
        if (this.__links[i].getInputNodeId() === nodeId) {
          connectedLinks.push(this.__links[i].getLinkId());
        }
        if (this.__links[i].getOutputNodeId() === nodeId) {
          connectedLinks.push(this.__links[i].getLinkId());
        }
      }
      return connectedLinks;
    },

    __getLink: function(id) {
      for (let i = 0; i < this.__links.length; i++) {
        if (this.__links[i].getLinkId() === id) {
          return this.__links[i];
        }
      }
      return null;
    },

    __removeNode: function(node) {
      if (node.getMetaData().type == "dynamic") {
        const slotName = "stopDynamic";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        let data = {
          nodeId: node.getNodeId()
        };
        socket.emit(slotName, data);
      }

      this.__desktop.remove(node);
      let index = this.__nodes.indexOf(node);
      if (index > -1) {
        this.__nodes.splice(index, 1);
      }
    },

    __removeAllNodes: function() {
      while (this.__nodes.length > 0) {
        this.__removeNode(this.__nodes[this.__nodes.length-1]);
      }
    },

    __removeLink: function(link) {
      let node2 = this.getNode(link.getOutputNodeId());
      if (node2) {
        node2.getPropsWidget().enableProp(link.getOutputPortId(), true);
      }

      this.__svgWidget.removeCurve(link.getRepresentation());
      let index = this.__links.indexOf(link);
      if (index > -1) {
        this.__links.splice(index, 1);
      }
    },

    __removeAllLinks: function() {
      while (this.__links.length > 0) {
        this.__removeLink(this.__links[this.__links.length-1]);
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    __getInputPortLinked: function(nodeId, inputPortId) {
      for (let i = 0; i < this.__links.length; i++) {
        const link = this.__links[i];
        if (link.getOutputNodeId() === nodeId && link.getOutputPortId() === inputPortId) {
          return {
            nodeUuid: link.getInputNodeId(),
            output: link.getInputPortId()
          };
        }
      }
      return null;
    },

    __loadProject: function() {
      this.removeAll();

      if (this.__workbenchData) {
        let workbenchData = this.__workbenchData;
        for (let nodeUuid in workbenchData) {
          let nodeData = workbenchData[nodeUuid];
          const nodeImageId = nodeData.key + "-" + nodeData.version;
          let node = this.__createNode(nodeImageId, nodeUuid, nodeData);
          this.__addNodeToWorkbench(node, nodeData.position);
          this.__nodes.push(node);
        }
        for (let nodeUuid in workbenchData) {
          let nodeData = workbenchData[nodeUuid];
          if (nodeData.inputs) {
            for (let prop in nodeData.inputs) {
              let link = nodeData.inputs[prop];
              if (typeof link == "object" && link.nodeUuid) {
                this.__addLink({
                  nodeUuid: link.nodeUuid,
                  output: link.output
                }, {
                  nodeUuid: nodeUuid,
                  input: prop
                });
              }
            }
          }
        }
      }
    },

    saveProject: function() {
      const savePosition = true;
      this.__workbenchData = this.serializePipeline(savePosition);
    },

    serializePipeline: function(savePosition = false) {
      let workbench = {};
      for (let i = 0; i < this.__nodes.length; i++) {
        const node = this.__nodes[i];
        const nodeData = node.getMetaData();
        let cNode = workbench[node.getNodeId()] = {
          key: nodeData.key,
          version: nodeData.version,
          inputs: node.getInputValues(),
          outputs: {}
        };
        if (savePosition) {
          cNode.position = {
            x: node.getCurrentBounds().left,
            y: node.getCurrentBounds().top
          };
        }
        for (let key in node.getInputPorts()) {
          const linkPort = this.__getInputPortLinked(node.getNodeId(), key);
          if (linkPort) {
            cNode.inputs[key] = linkPort;
          }
        }
        for (let key in nodeData.outputs) {
          const outputPort = nodeData.outputs[key];
          if ("value" in outputPort) {
            cNode.outputs[key] = outputPort.value;
          }
        }
      }
      return workbench;
    },

    getWorkbenchData: function() {
      return this.__workbenchData;
    },

    addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();
    },

    clearProgressData: function() {
      for (let i = 0; i < this.__nodes.length; i++) {
        this.__nodes[i].setProgress(0);
      }
    },

    updateProgress: function(nodeId, progress) {
      let node = this.getNode(nodeId);
      node.setProgress(progress);
    },

    __selectedItemChanged: function(newID) {
      if (newID === this.__selectedItemId) {
        return;
      }

      let oldId = this.__selectedItemId;
      if (oldId) {
        if (this.__isSelectedItemALink(oldId)) {
          let unselectedLink = this.__getLink(oldId);
          const unselectedColor = qxapp.theme.Color.colors["workbench-link-active"];
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
