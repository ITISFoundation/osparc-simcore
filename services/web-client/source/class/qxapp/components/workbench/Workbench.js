/**
 *
 * @asset(qxapp/icons/workbench/*)
 */

/* global qxapp */
/* eslint new-cap: [2, {capIsNewExceptions: ["Set"]}] */
/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let canvas = new qx.ui.layout.Canvas();
    this.set({
      layout: canvas
    });

    this._svgWidget = new qxapp.components.workbench.SvgWidget();
    this.add(this._svgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this._svgWidget.addListener("SvgWidgetReady", function() {
      // Will be called only the first time Svg lib is loaded
      this._deserializeData();
    }, this);

    this._svgWidget.addListener("SvgWidgetReady", function() {
      this._svgWidget.addListener("appear", function() {
        // Will be called once Svg lib is loaded and appears
        this._deserializeData();
      }, this);
    }, this);

    this._desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.add(this._desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this._nodes = [];
    this._links = [];

    this._plusButton = this._getPlusButton();
    this.add(this._plusButton, {
      right: 20,
      bottom: 20
    });
    let scope = this;
    this._plusButton.addListener("execute", function() {
      scope._plusButton.setMenu(scope._getMatchingServicesMenu());
    }, scope);
    this._plusButtonCount = 0;

    let playButton = this._getPlayButton();
    this.add(playButton, {
      right: 50+20+20,
      bottom: 20
    });
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    _nodes: null,
    _links: null,
    _desktop: null,
    _svgWidget: null,
    _plusButton: null,
    _selection: null,
    __myData: null,

    _getPlusButton: function() {
      // TODO: change icon
      const icon = qxapp.utils.Placeholders.getIcon("fa-plus", 32); // "qxapp/icons/workbench/add-icon.png"
      let plusButton = new qx.ui.form.MenuButton(null, icon, this._getMatchingServicesMenu());
      plusButton.set({
        width: 50,
        height: 50
      });
      return plusButton;
    },

    _getMatchingServicesMenu: function() {
      let menuNodeTypes = new qx.ui.menu.Menu();

      let producersButton = new qx.ui.menu.Button("Producers", null, null, this._getProducers());
      menuNodeTypes.add(producersButton);
      let computationalsButton = new qx.ui.menu.Button("Computationals", null, null, this._getComputationals());
      menuNodeTypes.add(computationalsButton);
      let analysesButton = new qx.ui.menu.Button("Analyses", null, null, this._getAnalyses());
      menuNodeTypes.add(analysesButton);

      return menuNodeTypes;
    },

    _getPlayButton: function() {
      // TODO: change icon
      const icon = qxapp.utils.Placeholders.getIcon("fa-play", 32); // ""qxapp/icons/workbench/play-icon.png""
      let playButton = new qx.ui.form.Button(null, icon);
      playButton.set({
        width: 50,
        height: 50
      });

      let scope = this;
      playButton.addListener("execute", function() {
        let pipelineData = scope._serializeData();
        console.log(pipelineData);
      }, scope);

      return playButton;
    },

    _createMenuFromList: function(nodesList) {
      let buttonsListMenu = new qx.ui.menu.Menu();

      nodesList.forEach(node => {
        let nodeButton = new qx.ui.menu.Button(node.name);

        let scope = this;
        nodeButton.addListener("execute", function() {
          let nodeItem = scope._createNode(node);
          scope._addNodeToWorkbench(nodeItem);
          scope._createLinkToLast();
        }, scope);

        buttonsListMenu.add(nodeButton);
      });

      return buttonsListMenu;
    },

    _addNodeToWorkbench(node, position) {
      if (position === undefined) {
        let nNodes = this._nodes.length;
        node.moveTo(50 + nNodes*250, 200);
        this._desktop.add(node);
        node.open();
        this._nodes.push(node);
      } else {
        node.moveTo(position.x, position.y);
        this._desktop.add(node);
        node.open();
        this._nodes.push(node);
      }
    },

    _createLinkToLast: function(node) {
      let nNodes = this._nodes.length;
      if (nNodes > 1) {
        // force rendering to get the node's updated position
        qx.ui.core.queue.Layout.flush();
        this._addLink(this._nodes[nNodes-2], this._nodes[nNodes-1]);
      }
    },

    _createNode: function(node) {
      let nodeBase = new qxapp.components.workbench.NodeBase(node);

      if (nodeBase.getNodeImageId() === "modeler") {
        const slotName = "startModeler";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        socket.on(slotName, function(val) {
          if (val["service_uuid"] === nodeBase.getNodeId()) {
            let portNumber = val["containers"][0]["published_ports"];
            nodeBase.getMetaData().viewer.port = portNumber;
          }
        }, this);
        socket.emit(slotName, nodeBase.getNodeId());
      } else if (nodeBase.getNodeImageId() === "jupyter-base-notebook") {
        const slotName = "startJupyter";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        socket.on(slotName, function(val) {
          if (val["service_uuid"] === nodeBase.getNodeId()) {
            let portNumber = val["containers"][0]["published_ports"];
            nodeBase.getMetaData().viewer.port = portNumber;
          }
        }, this);
        socket.emit(slotName, nodeBase.getNodeId());
      }

      let scope = this;
      nodeBase.addListener("move", function(e) {
        let linksInvolved = new Set([]);
        nodeBase.getInputLinkIDs().forEach(linkId => {
          linksInvolved.add(linkId);
        });
        nodeBase.getOutputLinkIDs().forEach(linkId => {
          linksInvolved.add(linkId);
        });

        linksInvolved.forEach(linkId => {
          let link = scope._getLink(linkId);
          if (link) {
            let node1 = scope._getNode(link.getInputNodeId());
            let node2 = scope._getNode(link.getOutputNodeId());
            const pointList = scope._getLinkPoints(node1, node2);
            const x1 = pointList[0][0];
            const y1 = pointList[0][1];
            const x2 = pointList[1][0];
            const y2 = pointList[1][1];
            scope._svgWidget.updateCurve(link.getRepresentation(), x1, y1, x2, y2);
          }
        });
      }, scope);

      nodeBase.addListener("dblclick", function(e) {
        scope.fireDataEvent("NodeDoubleClicked", nodeBase);
      }, scope);

      return nodeBase;
    },

    _addLink: function(node1, node2) {
      const pointList = this._getLinkPoints(node1, node2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this._svgWidget.drawCurve(x1, y1, x2, y2);
      let linkBase = new qxapp.components.workbench.LinkBase(linkRepresentation);
      linkBase.setInputNodeId(node1.getNodeId());
      linkBase.setOutputNodeId(node2.getNodeId());
      node1.addOutputLinkID(linkBase.getLinkId());
      node2.addInputLinkID(linkBase.getLinkId());
      this._links.push(linkBase);

      linkBase.getRepresentation().node.addEventListener("click", function(e) {

      });
    },

    _getLinkPoints: function(node1, node2) {
      const node1Pos = node1.getBounds();
      const node2Pos = node2.getBounds();

      const x1 = node1Pos.left + node1Pos.width;
      const y1 = node1Pos.top + 50;
      const x2 = node2Pos.left;
      const y2 = node2Pos.top + 50;
      return [[x1, y1], [x2, y2]];
    },

    _getNode: function(id) {
      for (let i = 0; i < this._nodes.length; i++) {
        if (this._nodes[i].getNodeId() === id) {
          return this._nodes[i];
        }
      }
      return null;
    },

    _getLink: function(id) {
      for (let i = 0; i < this._links.length; i++) {
        if (this._links[i].getLinkId() === id) {
          return this._links[i];
        }
      }
      return null;
    },

    _getConnectedLinks: function(id) {
      let connectedLinks = Set([]);
      this._links.forEach(link => {
        if (link.getInputNodeId() === id) {
          connectedLinks.add(link.getLinkId());
        }
        if (link.getOutputNodeId() === id) {
          connectedLinks.add(link.getLinkId());
        }
      });
      return connectedLinks;
    },

    _addModeler: function() {
      const minWidth = 400;
      const minHeight = 400;

      let win = new qx.ui.window.Window("Modeler");
      win.setLayout(new qx.ui.layout.VBox());
      win.setMinWidth(minWidth);
      win.setMinHeight(minHeight);
      win.setAllowMaximize(false);
      win.open();

      let threeWidget = new qxapp.components.workbench.ThreeWidget(minWidth, minHeight, "#3F3F3F");
      win.add(threeWidget, {
        flex: 1
      });

      win.addListener("resize", function(e) {
        threeWidget.viewResized(e.getData().width, e.getData().height);
      }, this);
    },

    _serializeData: function() {
      let pipeline = {};
      for (let i = 0; i < this._nodes.length; i++) {
        const nodeId = this._nodes[i].getNodeId();
        pipeline[nodeId] = {};
        pipeline[nodeId].serviceId = this._nodes[i].getMetaData().id;
        pipeline[nodeId].input = this._nodes[i].getMetaData().input;
        pipeline[nodeId].output = this._nodes[i].getMetaData().output;
        pipeline[nodeId].settings = this._nodes[i].getMetaData().settings;
        pipeline[nodeId].children = [];
        for (let j = 0; j < this._links.length; j++) {
          if (nodeId === this._links[j].getInputNodeId()) {
            pipeline[nodeId].children.push(this._links[j].getOutputNodeId());
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

    __removeNode: function(node) {
      this._desktop.remove(node);
    },

    __removeAllNodes: function() {
      while (this._nodes.length > 0) {
        this.__removeNode(this._nodes[this._nodes.length-1]);
        this._nodes.pop();
      }
    },

    __removeLink: function(link) {
      this._svgWidget.removeCurve(link.getRepresentation());
    },

    __removeAllLinks: function() {
      while (this._links.length > 0) {
        this.__removeLink(this._links[this._links.length-1]);
        this._links.pop();
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    _deserializeData: function() {
      console.log("__myData", this.__myData);
      if (this.__myData === null) {
        this.removeAll();
        return;
      }

      // add nodes
      for (let i = 0; i < this.__myData.length; i++) {
        let nodeItem = this._createNode(this.__myData[i]);
        nodeItem.setNodeId(this.__myData[i].uuid);
        if (Object.prototype.hasOwnProperty.call(this.__myData[i], "position")) {
          this._addNodeToWorkbench(nodeItem, this.__myData[i].position);
        } else {
          this._addNodeToWorkbench(nodeItem);
        }
      }

      qx.ui.core.queue.Layout.flush();

      // add links
      for (let i = 0; i < this.__myData.length; i++) {
        if (this.__myData[i].children.length > 0) {
          let node1 = this._getNode(this.__myData[i].uuid);
          for (let j = 0; j < this.__myData[i].children.length; j++) {
            let node2 = this._getNode(this.__myData[i].children[j]);
            this._addLink(node1, node2);
          }
        }
      }
    },

    _getProducers: function() {
      const producers = qxapp.data.Fake.getProducers();
      return this._createMenuFromList(producers);
    },

    _getComputationals: function() {
      const computationals = qxapp.data.Fake.getComputationals();
      return this._createMenuFromList(computationals);
    },

    _getAnalyses: function() {
      const analyses = qxapp.data.Fake.getAnalyses();
      return this._createMenuFromList(analyses);
    }
  }
});
