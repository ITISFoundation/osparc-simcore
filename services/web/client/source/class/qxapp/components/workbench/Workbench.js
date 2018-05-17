/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let canvas = new qx.ui.layout.Canvas();
    this.set({
      layout: canvas
    });

    this.__svgWidget = new qxapp.components.workbench.SvgWidget();
    this.add(this.__svgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

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

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__nodes = [];
    this.__links = [];

    let plusButton = this.__getPlusButton();
    this.add(plusButton, {
      right: 20,
      bottom: 20
    });
    plusButton.addListener("execute", function() {
      plusButton.setMenu(this.__getMatchingServicesMenu());
    }, this);

    let playButton = this.__getPlayButton();
    this.add(playButton, {
      right: 50+20+20,
      bottom: 20
    });
    playButton.addListener("execute", function() {
      let pipelineDataStructure = this.__serializeData();
      console.log(pipelineDataStructure);
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __nodes: null,
    __links: null,
    __desktop: null,
    __svgWidget: null,
    __tempLinkNodeId: null,
    __tempLinkPortId: null,
    __tempLinkRepr: null,

    __getPlusButton: function() {
      const icon = "@FontAwesome5Solid/plus/32"; // qxapp.utils.Placeholders.getIcon("fa-plus", 32);
      let plusButton = new qx.ui.form.MenuButton(null, icon, this.__getMatchingServicesMenu());
      plusButton.set({
        width: 50,
        height: 50
      });
      return plusButton;
    },

    __getMatchingServicesMenu: function() {
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
        width: 50,
        height: 50
      });
      return playButton;
    },

    __createMenuFromList: function(nodesList) {
      let buttonsListMenu = new qx.ui.menu.Menu();

      nodesList.forEach(node => {
        let nodeButton = new qx.ui.menu.Button(node.name);

        nodeButton.addListener("execute", function() {
          let nodeItem = this.__createNode(node);
          this.__addNodeToWorkbench(nodeItem);
          // this.__createLinkToLastNode();
        }, this);

        buttonsListMenu.add(nodeButton);
      });

      return buttonsListMenu;
    },

    __addNodeToWorkbench: function(node, position) {
      if (position === undefined) {
        let farthestRight = 0;
        for (let i=0; i < this.__nodes.length; i++) {
          let boundPos = this.__nodes[i].getBounds();
          let rightPos = boundPos.left + boundPos.width;
          if (farthestRight < rightPos) {
            farthestRight = rightPos;
          }
        }
        node.moveTo(50 + farthestRight, 200);
        this.__desktop.add(node);
        node.open();
        this.__nodes.push(node);
      } else {
        node.moveTo(position.x, position.y);
        this.__desktop.add(node);
        node.open();
        this.__nodes.push(node);
      }

      node.addListener("move", function(e) {
        let linksInvolved = new Set([]);
        node.getInputLinkIDs().forEach(linkId => {
          linksInvolved.add(linkId);
        });
        node.getOutputLinkIDs().forEach(linkId => {
          linksInvolved.add(linkId);
        });

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
      }, this);

      node.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", node);
      }, this);
    },
    /*
    __createLinkToLastNode: function() {
      let nNodes = this.__nodes.length;
      if (nNodes > 1) {
        // force rendering to get the node's updated position
        qx.ui.core.queue.Layout.flush();
        let node1 = this.__nodes[nNodes-2];
        let port1 = node1.getOutputPorts()[0];
        let node2 = this.__nodes[nNodes-1];
        let port2 = node2.getInputPorts()[0];
        if (port1 !== undefined && port2 !== undefined) {
          this.__addLink(node1, port1, node2, port2);
        }
      }
    },
    */
    __createNode: function(node) {
      let nodeBase = new qxapp.components.workbench.NodeBase();
      nodeBase.setMetadata(node);

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
      nodeBase.addListener("StartTempConn", function(e) {
        this.__tempLinkNodeId = e.getData()[0];
        this.__tempLinkPortId = e.getData()[1];
        qx.bom.Element.addListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);
      nodeBase.addListener("EndTempConn", function(e) {
        let nodeId = e.getData()[0];
        let portId = e.getData()[1];
        if (nodeId !== null && portId !== null) {
          this.__endTempLink(nodeId, portId);
        }
        this.__removeTempLink();
        qx.bom.Element.removeListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);

      return nodeBase;
    },

    __addLink: function(node1, port1, node2, port2, linkId) {
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
      node1.addOutputLinkID(linkBase.getLinkId());
      node2.addInputLinkID(linkBase.getLinkId());
      this.__links.push(linkBase);

      linkBase.getRepresentation().node.addEventListener("click", function(e) {
        console.log("Link selected", e.getData(e));
      });

      return linkBase;
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
      if (port.isInput) {
        x1 = pointerEvent.getViewportLeft();
        y1 = pointerEvent.getViewportTop() - navBarHeight;
        x2 = portPos[0];
        y2 = portPos[1];
      } else {
        x1 = portPos[0];
        y1 = portPos[1];
        x2 = pointerEvent.getViewportLeft();
        y2 = pointerEvent.getViewportTop() - navBarHeight;
      }

      if (this.__tempLinkRepr === null) {
        this.__tempLinkRepr = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      } else {
        this.__svgWidget.updateCurve(this.__tempLinkRepr, x1, y1, x2, y2);
      }
    },

    __endTempLink: function(nodeId, portId) {
      if (this.__tempLinkNodeId === null || this.__tempLinkPortId === null) {
        return;
      }
      let node1 = this.__getNode(this.__tempLinkNodeId);
      if (node1 === null) {
        return;
      }
      let port1 = node1.getPort(this.__tempLinkPortId);
      if (port1 === null) {
        return;
      }
      let node2 = this.__getNode(nodeId);
      if (node2 === null) {
        return;
      }
      let port2 = node2.getPort(portId);
      if (port2 === null) {
        return;
      }

      this.__addLink(node1, port1, node2, port2);
    },

    __removeTempLink: function() {
      if (this.__tempLinkRepr !== null) {
        this.__svgWidget.removeCurve(this.__tempLinkRepr);
      }
      this.__tempLinkRepr = null;
      this.__tempLinkNodeId = null;
      this.__tempLinkPortId = null;
    },

    __getLinkPoint: function(node, port) {
      const nodeBounds = node.getBounds();
      const portIdx = node.getPortIndex(port.portId);
      let x = nodeBounds.left;
      let y = nodeBounds.top + 4 + 33 + 10 + 16/2 + (16+5)*portIdx;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      return [x, y];
    },

    __getLinkPoints: function(node1, port1, node2, port2) {
      let p1 = this.__getLinkPoint(node1, port1);
      let p2 = this.__getLinkPoint(node2, port2);
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
    },

    __removeAllNodes: function() {
      while (this.__nodes.length > 0) {
        this.__removeNode(this.__nodes[this.__nodes.length-1]);
        this.__nodes.pop();
      }
    },

    __removeLink: function(link) {
      this.__svgWidget.removeCurve(link.getRepresentation());
    },

    __removeAllLinks: function() {
      while (this.__links.length > 0) {
        this.__removeLink(this.__links[this.__links.length-1]);
        this.__links.pop();
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    __serializeData: function() {
      let pipeline = {};
      for (let i = 0; i < this.__nodes.length; i++) {
        const nodeId = this.__nodes[i].getNodeId();
        pipeline[nodeId] = {};
        pipeline[nodeId].serviceId = this.__nodes[i].getMetadata().id;
        pipeline[nodeId].inputs = this.__nodes[i].getMetadata().inputs;
        pipeline[nodeId].outputs = this.__nodes[i].getMetadata().outputs;
        pipeline[nodeId].settings = this.__nodes[i].getMetadata().settings;
        pipeline[nodeId].children = [];
        for (let j = 0; j < this.__links.length; j++) {
          if (nodeId === this.__links[j].getInputNodeId()) {
            // TODO: add portID
            pipeline[nodeId].children.push(this.__links[j].getOutputNodeId());
          }
        }
      }
      // remove nodes with no offspring
      for (let nodeId in pipeline) {
        if (Object.prototype.hasOwnProperty.call(pipeline, nodeId)) {
          if (pipeline[nodeId].children.length === 0) {
            delete pipeline[nodeId];
          }
        }
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
      let nodes = this.__myData.nodes;
      for (let i = 0; i < nodes.length; i++) {
        let nodeUi = this.__createNode(nodes[i]);
        nodeUi.setNodeId(nodes[i].uuid);
        if (Object.prototype.hasOwnProperty.call(nodes[i], "position")) {
          this.__addNodeToWorkbench(nodeUi, nodes[i].position);
        } else {
          this.__addNodeToWorkbench(nodeUi);
        }
      }

      qx.ui.core.queue.Layout.flush();

      // add links
      let links = this.__myData.links;
      for (let i = 0; i < links.length; i++) {
        let node1 = this.__getNode(links[i].node1Id);
        let port1 = node1.getPort(links[i].port1Id);
        let node2 = this.__getNode(links[i].node2Id);
        let port2 = node2.getPort(links[i].port2Id);
        this.__addLink(node1, port1, node2, port2, links[i].linkId);
      }
    },

    addWindowToDesktop(node) {
      this.__desktop.add(node);
      node.open();
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
