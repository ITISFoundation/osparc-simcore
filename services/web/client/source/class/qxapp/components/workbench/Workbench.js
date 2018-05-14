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

    __getPlusButton: function() {
      const icon = qxapp.utils.Placeholders.getIcon("fa-plus", 32);
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
      const icon = qxapp.utils.Placeholders.getIcon("fa-play", 32);
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
          this.__createLinkToLastNode();
        }, this);

        buttonsListMenu.add(nodeButton);
      });

      return buttonsListMenu;
    },

    __addNodeToWorkbench: function(node, position) {
      if (position === undefined) {
        let nNodes = this.__nodes.length;
        node.moveTo(50 + nNodes*250, 200);
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
            let node2 = this.__getNode(link.getOutputNodeId());
            const pointList = this.__getLinkPoints(node1, node2);
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

    __createLinkToLastNode: function() {
      let nNodes = this.__nodes.length;
      if (nNodes > 1) {
        // force rendering to get the node's updated position
        qx.ui.core.queue.Layout.flush();
        this.__addLink(this.__nodes[nNodes-2], this.__nodes[nNodes-1]);
      }
    },

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
        nodeBase.getMetadata().viewer.port = 1234;
      }

      return nodeBase;
    },

    __addLink: function(node1, node2) {
      const pointList = this.__getLinkPoints(node1, node2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__svgWidget.drawCurve(x1, y1, x2, y2);
      let linkBase = new qxapp.components.workbench.LinkBase(linkRepresentation);
      linkBase.setInputNodeId(node1.getNodeId());
      linkBase.setOutputNodeId(node2.getNodeId());
      node1.addOutputLinkID(linkBase.getLinkId());
      node2.addInputLinkID(linkBase.getLinkId());
      this.__links.push(linkBase);

      linkBase.getRepresentation().node.addEventListener("click", function(e) {

      });
    },

    __getLinkPoints: function(node1, node2) {
      const node1Pos = node1.getBounds();
      const node2Pos = node2.getBounds();

      const x1 = node1Pos.left + node1Pos.width;
      const y1 = node1Pos.top + 50;
      const x2 = node2Pos.left;
      const y2 = node2Pos.top + 50;
      return [[x1, y1], [x2, y2]];
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
        pipeline[nodeId].input = this.__nodes[i].getMetadata().input;
        pipeline[nodeId].output = this.__nodes[i].getMetadata().output;
        pipeline[nodeId].settings = this.__nodes[i].getMetadata().settings;
        pipeline[nodeId].children = [];
        for (let j = 0; j < this.__links.length; j++) {
          if (nodeId === this.__links[j].getInputNodeId()) {
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
      console.log("__myData", this.__myData);

      this.removeAll();
      if (this.__myData === null) {
        return;
      }

      // add nodes
      for (let i = 0; i < this.__myData.length; i++) {
        let nodeItem = this.__createNode(this.__myData[i]);
        nodeItem.setNodeId(this.__myData[i].uuid);
        if (Object.prototype.hasOwnProperty.call(this.__myData[i], "position")) {
          this.__addNodeToWorkbench(nodeItem, this.__myData[i].position);
        } else {
          this.__addNodeToWorkbench(nodeItem);
        }
      }

      qx.ui.core.queue.Layout.flush();

      // add links
      for (let i = 0; i < this.__myData.length; i++) {
        if (this.__myData[i].children.length > 0) {
          let node1 = this.__getNode(this.__myData[i].uuid);
          for (let j = 0; j < this.__myData[i].children.length; j++) {
            let node2 = this.__getNode(this.__myData[i].children[j]);
            this.__addLink(node1, node2);
          }
        }
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
