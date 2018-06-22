/* eslint no-warning-comments: "off" */

const BUTTON_SIZE = 50;
const BUTTON_SPACING = 10;

qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function() {
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

    this.__svgWidget = new qxapp.components.workbench.SvgWidget();
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

    this.__svgWidget.addListener("SvgWidgetReady", function() {
      // Will be called only the first time Svg lib is loaded
      this.__deserializeData();
    }, this);

    this.__svgWidget.addListener("SvgWidgetReady", function() {
      this.__svgWidget.addListener("appear", function() {
        // Will be called once Svg lib is loaded and appears
        this.__deserializeData();
      }, this);
    }, this);


    this.__logger = new qxapp.components.workbench.logger.LoggerView();
    this.__desktop.add(this.__logger);

    this.__nodes = [];
    this.__links = [];

    let loggerButton = this.__getShowLoggerButton();
    this.add(loggerButton, {
      left: 20,
      bottom: 20
    });

    let buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(BUTTON_SPACING));
    this.add(buttonContainer, {
      bottom: 20,
      right: 20
    });
    [
      this.__getPlusMenuButton(),
      this.__getRemoveButton(),
      this.__getPlayButton(),
      this.__getStopButton()
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
    canStart: {
      nullable: false,
      init: true,
      check: "Boolean",
      apply : "__applyCanStart"
    }
  },

  members: {
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

    __getShowLoggerButton: function() {
      const icon = "@FontAwesome5Solid/list-alt/32";
      let loggerButton = new qx.ui.form.Button(null, icon);
      loggerButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      loggerButton.addListener("execute", function() {
        const bounds = loggerButton.getBounds();
        loggerButton.hide();
        this.__logger.moveTo(bounds.left, bounds.top+bounds.height - this.__logger.getHeight());
        this.__logger.open();
        this.__logger.addListenerOnce("close", function() {
          loggerButton.show();
        }, this);
      }, this);
      return loggerButton;
    },

    __getPlusButton: function() {
      const icon = "@FontAwesome5Solid/plus/32"; // qxapp.utils.Placeholders.getIcon("fa-plus", 32);
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

    __getPlusMenuButton: function() {
      const icon = "@FontAwesome5Solid/plus/32"; // qxapp.utils.Placeholders.getIcon("fa-plus", 32);
      let plusButton = new qx.ui.form.MenuButton(null, icon, this.__getServicesMenu());
      plusButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });
      plusButton.addListener("execute", function() {
        plusButton.setMenu(this.__getServicesMenu());
      }, this);
      return plusButton;
    },

    __getServicesMenu: function() {
      let menuNodeTypes = new qx.ui.menu.Menu();

      let producersButton = new qx.ui.menu.Button("Producers", null, null, this.__getProducers());
      menuNodeTypes.add(producersButton);
      let computationalsButton = new qx.ui.menu.Button("Computationals", null, null, this.__getComputationals());
      menuNodeTypes.add(computationalsButton);
      let analysesButton = new qx.ui.menu.Button("Analyses", null, null, this.__getAnalyses());
      menuNodeTypes.add(analysesButton);

      return menuNodeTypes;
    },

    __getPlayButton: function() {
      const icon = "@FontAwesome5Solid/play/32";
      let playButton = new qx.ui.form.Button(null, icon);
      playButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });

      playButton.addListener("execute", function() {
        let socket = qxapp.wrappers.WebSocket.getInstance();

        // callback for incoming logs
        if (!socket.slotExists("logger")) {
          socket.on("logger", function(data) {
            var d = JSON.parse(data);
            var node = d["Node"];
            var msg = d["Message"];
            this.__updateLogger(node, msg);
          }, this);
        }
        socket.emit("logger");

        // callback for incoming progress
        if (!socket.slotExists("progress")) {
          socket.on("progress", function(data) {
            console.log("progress", data);
            var d = JSON.parse(data);
            var node = d["Node"];
            var progress = 100*Number.parseFloat(d["Progress"]).toFixed(4);
            this.updateProgress(node, progress);
          }, this);
        }

        if (this.getCanStart()) {
          this.__startPipeline();
        }
      }, this);

      return playButton;
    },

    __getStopButton: function() {
      const icon = "@FontAwesome5Solid/stop-circle/32";
      let stopButton = new qx.ui.form.Button(null, icon);
      stopButton.set({
        width: BUTTON_SIZE,
        height: BUTTON_SIZE
      });

      stopButton.addListener("execute", function() {
        this.__stopPipeline();
      }, this);
      return stopButton;
    },

    __applyCanStart: function(value, old) {
      console.log("CanStart", value);
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
      let nodeMetaData = data.service;
      let nodeAId = data.contextNodeId;
      let portA = data.contextPort;

      let nodeB = this.__createNode(nodeMetaData);
      this.__addNodeToWorkbench(nodeB, pos);

      if (nodeAId !== null && portA !== null) {
        let nodeA = this.__getNode(nodeAId);
        let portB = this.__findCompatiblePort(nodeB, portA);
        this.__addLink(nodeA, portA, nodeB, portB);
      }
    },

    __createMenuFromList: function(nodesList) {
      let buttonsListMenu = new qx.ui.menu.Menu();

      nodesList.forEach(nodeMetaData => {
        let nodeButton = new qx.ui.menu.Button(nodeMetaData.label);
        nodeButton.addListener("execute", function() {
          let nodeItem = this.__createNode(nodeMetaData);
          this.__addNodeToWorkbench(nodeItem);
        }, this);

        buttonsListMenu.add(nodeButton);
      });

      return buttonsListMenu;
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
        this.addWindowToDesktop(node);
        this.__nodes.push(node);
      } else {
        node.moveTo(position.x, position.y);
        this.addWindowToDesktop(node);
        this.__nodes.push(node);
      }

      node.addListener("NodeMoving", function() {
        this.__updateLinks(node);
      }, this);

      node.addListener("appear", function() {
        this.__updateLinks(node);
      }, this);

      node.addListener("dblclick", function(e) {
        if (node.getMetadata().key === "FileManager") {
          let win = new qx.ui.window.Window(node.getMetadata().name).set({
            width: 800,
            height: 600,
            minWidth: 400,
            minHeight: 400,
            modal: true,
            showMinimize: false,
            layout: new qx.ui.layout.Canvas()
          });
          win.moveTo(50, 50);

          let fileManager = new qxapp.components.workbench.widgets.FileManager();
          win.add(fileManager, {
            left: 0,
            top: 0,
            right: 0,
            bottom: 0
          });
          fileManager.addListener("FileSelected", function(data) {
            node.getMetadata().outputs[0].value = data.getData().filePath;
            node.setProgress(100);
            win.close();
          }, this);

          this.addWindowToDesktop(win);
        } else {
          this.fireDataEvent("NodeDoubleClicked", node);
        }
        e.stopPropagation();
      }, this);

      qx.ui.core.queue.Layout.flush();
    },

    __createNode: function(nodeMetaData) {
      let nodeBase = new qxapp.components.workbench.NodeBase();
      nodeBase.setMetadata(nodeMetaData);

      if (nodeBase.getNodeImageId() === "modeler") {
        const slotName = "startModeler";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        socket.on(slotName, function(val) {
          if (val["service_uuid"] === nodeBase.getNodeId()) {
            let portNumber = val["containers"][0]["published_ports"];
            nodeBase.getMetadata().viewer.port = portNumber;
          }
        }, this);
        socket.emit(slotName, nodeBase.getNodeId());
      } else if (nodeBase.getNodeImageId() === "jupyter-base-notebook") {
        const slotName = "startJupyter";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        socket.on(slotName, function(val) {
          if (val["service_uuid"] === nodeBase.getNodeId()) {
            let portNumber = val["containers"][0]["published_ports"];
            nodeBase.getMetadata().viewer.port = portNumber;
          }
        }, this);
        socket.emit(slotName, nodeBase.getNodeId());
      }

      const evType = "pointermove";
      nodeBase.addListener("LinkDragStart", function(e) {
        let data = e.getData();
        let event = data.event;
        let dragNodeId = data.nodeId;
        let dragPortId = data.portId;

        // Register supported actions
        event.addAction("move");

        // Register supported types
        event.addType("osparc-metadata");
        let dragData = {
          dragNodeId: dragNodeId,
          dragPortId: dragPortId
        };
        event.addData("osparc-metadata", dragData);

        this.__tempLinkNodeId = dragData.dragNodeId;
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
        let dropPortId = data.portId;

        let compatible = false;
        if (event.supportsType("osparc-metadata")) {
          const dragNodeId = event.getData("osparc-metadata").dragNodeId;
          const dragPortId = event.getData("osparc-metadata").dragPortId;
          const dragTarget = this.__getNode(dragNodeId).getPort(dragPortId);
          const dropTarget = this.__getNode(dropNodeId).getPort(dropPortId);
          compatible = this.__arePortsCompatible(dragTarget, dropTarget);
        }

        if (!compatible) {
          event.preventDefault();
        }
      }, this);

      nodeBase.addListener("LinkDrop", function(e) {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropPortId = data.portId;

        if (event.supportsType("osparc-metadata")) {
          let dragNodeId = event.getData("osparc-metadata").dragNodeId;
          let dragPortId = event.getData("osparc-metadata").dragPortId;
          let nodeA = this.__getNode(dragNodeId);
          let portA = nodeA.getPort(dragPortId);
          let nodeB = this.__getNode(dropNodeId);
          let portB = nodeB.getPort(dropPortId);
          this.__addLink(nodeA, portA, nodeB, portB);
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
          srvCat.setContext(dragNodeId, this.__getNode(dragNodeId).getPort(dragPortId));
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

    __arePortsCompatible: function(port1, port2) {
      let compatible = (port1.portType === port2.portType);
      compatible = compatible && (port1.isInput !== port2.isInput);
      return compatible;
    },

    __findCompatiblePort: function(nodeB, portA) {
      if (portA.isInput) {
        let portsB = nodeB.getOutputPorts();
        for (let i = 0; i < portsB.length; i++) {
          if (portA.portType === portsB[i].portType) {
            return portsB[i];
          }
        }
      } else {
        let portsB = nodeB.getInputPorts();
        for (let i = 0; i < portsB.length; i++) {
          if (portA.portType === portsB[i].portType) {
            return portsB[i];
          }
        }
      }
      return null;
    },

    __addLink: function(node1, port1, node2, port2, linkId) {
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }

      const pointList = this.__getLinkPoints(node1, port1, node2, port2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      let linkBase = new qxapp.components.workbench.LinkBase(linkRepresentation);
      linkBase.setInputNodeId(node1.getNodeId());
      linkBase.setInputPortId(port1.portId);
      linkBase.setOutputNodeId(node2.getNodeId());
      linkBase.setOutputPortId(port2.portId);
      if (linkId !== undefined) {
        linkBase.setLinkId(linkId);
      }
      this.__links.push(linkBase);

      node2.getPropsWidget().enableProp(port2.portId, false);

      linkBase.getRepresentation().node.addEventListener("click", function(e) {
        // this is needed to get out of the context of svg
        linkBase.fireDataEvent("linkSelected", linkBase.getLinkId());
        e.stopPropagation();
      }, this);

      linkBase.addListener("linkSelected", function(e) {
        this.__selectedItemChanged(linkBase.getLinkId());
      }, this);

      return linkBase;
    },

    __updateLinks: function(node) {
      let linksInvolved = this.__getConnectedLinks(node.getNodeId());

      linksInvolved.forEach(linkId => {
        let link = this.__getLink(linkId);
        if (link) {
          let node1 = this.__getNode(link.getInputNodeId());
          let port1 = node1.getPort(link.getInputPortId());
          let node2 = this.__getNode(link.getOutputNodeId());
          let port2 = node2.getPort(link.getOutputPortId());
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
      let node = this.__getNode(this.__tempLinkNodeId);
      if (node === null) {
        return;
      }
      let port = node.getPort(this.__tempLinkPortId);
      if (port === null) {
        return;
      }

      let x1;
      let y1;
      let x2;
      let y2;
      const portPos = this.__getLinkPoint(node, port);
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

    __getLinkPoint: function(node, port) {
      const nodeBounds = node.getCurrentBounds();
      const portIdx = node.getPortIndex(port.portId);
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      let y = nodeBounds.top + 4 + 33 + 10 + 16/2 + (16+5)*portIdx;
      return [x, y];
    },

    __getLinkPoints: function(node1, port1, node2, port2) {
      let p1 = null;
      let p2 = null;
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }
      p1 = this.__getLinkPoint(node1, port1);
      p2 = this.__getLinkPoint(node2, port2);
      // hack to place the arrow-head properly
      p2[0] -= 6;
      return [p1, p2];
    },

    __getNode: function(id) {
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
      let node2 = this.__getNode(link.getOutputNodeId());
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

    __serializeData: function() {
      let pipeline = {
        "nodes": [],
        "links": []
      };
      for (let i = 0; i < this.__nodes.length; i++) {
        let node = {};
        node["uuid"] = this.__nodes[i].getNodeId();
        node["key"] = this.__nodes[i].getMetadata().key;
        node["tag"] = this.__nodes[i].getMetadata().tag;
        node["name"] = this.__nodes[i].getMetadata().name;
        node["inputs"] = this.__nodes[i].getMetadata().inputs;
        node["outputs"] = this.__nodes[i].getMetadata().outputs;
        node["settings"] = this.__nodes[i].getMetadata().settings;
        pipeline["nodes"].push(node);
      }
      for (let i = 0; i < this.__links.length; i++) {
        let link = {};
        link["uuid"] = this.__links[i].getLinkId();
        link["node1Id"] = this.__links[i].getInputNodeId();
        link["port1Id"] = this.__links[i].getInputPortId();
        link["node2Id"] = this.__links[i].getOutputNodeId();
        link["port2Id"] = this.__links[i].getOutputPortId();
        pipeline["links"].push(link);
      }
      return pipeline;
    },

    setData: function(pipeData) {
      this.__myData = pipeData;
    },

    __deserializeData: function() {
      this.removeAll();
      if (this.__myData === null) {
        return;
      }

      // add nodes
      let nodesMetaData = this.__myData.nodes;
      for (let i = 0; i < nodesMetaData.length; i++) {
        let nodeMetaData = nodesMetaData[i];
        let node = this.__createNode(nodeMetaData);
        node.setNodeId(nodeMetaData.uuid);
        if (Object.prototype.hasOwnProperty.call(nodeMetaData, "position")) {
          this.__addNodeToWorkbench(node, nodeMetaData.position);
        } else {
          this.__addNodeToWorkbench(node);
        }
      }

      // add links
      let links = this.__myData.links;
      for (let i = 0; i < links.length; i++) {
        let node1 = this.__getNode(links[i].node1Id);
        let port1 = node1.getPort(links[i].port1Id);
        let node2 = this.__getNode(links[i].node2Id);
        let port2 = node2.getPort(links[i].port2Id);
        this.__addLink(node1, port1, node2, port2, links[i].uuid);
      }
    },

    addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();
    },

    __startPipeline: function() {
      // ui start pipeline
      this.__clearProgressData();

      // post pipeline
      let currentPipeline = this.__serializeData();
      console.log(currentPipeline);
      let req = new qx.io.request.Xhr();
      let data = {};
      data = currentPipeline;
      data["pipeline_mockup_id"] = qxapp.utils.Utils.uuidv4();
      req.set({
        url: "/start_pipeline",
        method: "POST",
        requestData: qx.util.Serializer.toJson(data)
      });
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.send();

      // FIXME: do we need this?
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.emit("logger");

      this.setCanStart(false);

      this.__logger.info("Workbench", "Starting pipeline");
    },

    __onPipelinesubmitted: function(e) {
      let req = e.getTarget();
      console.debug("Everything went fine!!");
      console.debug("status  : ", req.getStatus());
      console.debug("phase   : ", req.getPhase());
      console.debug("response: ", req.getResponse());

      // FIXME: do we need this?
      // register for log and progress
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.emit("register_for_log", "123");
      socket.emit("register_for_progress", "123");
    },

    __stopPipeline: function() {
      this.__clearProgressData();

      this.setCanStart(true);

      this.__logger.warn("Workbench", "Stopping pipeline");
    },

    __updateLogger: function(nodeId, msg) {
      let node = this.__getNode(nodeId);
      if (node) {
        this.__logger.info(node.getCaption(), msg);
      }
    },

    __clearProgressData: function() {
      for (let i = 0; i < this.__nodes.length; i++) {
        this.__nodes[i].setProgress(0);
      }
    },

    updateProgress: function(nodeId, progress) {
      let node = this.__getNode(nodeId);
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
    },

    __getProducers: function() {
      const producers = qxapp.data.Fake.getProducers();
      return this.__createMenuFromList(producers);
    },

    __getComputationals: function() {
      const computationals = qxapp.data.Fake.getComputationals();
      return this.__createMenuFromList(computationals);
    },

    __getAnalyses: function() {
      const analyses = qxapp.data.Fake.getAnalyses();
      return this.__createMenuFromList(analyses);
    }
  }
});
