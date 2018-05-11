qx.Class.define("qxapp.components.workbench.Workbench", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let canvas = new qx.ui.layout.Canvas();
    this.set({
      layout: canvas
    });

    this.__SvgWidget = new qxapp.components.workbench.SvgWidget();
    this.add(this.__SvgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__Desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.add(this.__Desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__Nodes = [];
    this.__Links = [];

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
      let pipelineDataStructure = this._serializePipelineDataStructure();
      console.log(pipelineDataStructure);
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __Nodes: null,
    __Links: null,
    __Desktop: null,
    __SvgWidget: null,

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
          this.__addNode(node);
        }, this);

        buttonsListMenu.add(nodeButton);
      });

      return buttonsListMenu;
    },

    __addNodeToWorkbench(node) {
      let nNodesB = this.__Nodes.length;
      node.moveTo(50 + nNodesB*250, 200);
      this.__Desktop.add(node);
      node.open();
      this.__Nodes.push(node);

      // force rendering to get the node"s updated position
      qx.ui.core.queue.Layout.flush();

      let nNodesA = this.__Nodes.length;
      if (nNodesA > 1) {
        this.__addLink(this.__Nodes[nNodesA-2], this.__Nodes[nNodesA-1]);
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
            this.__SvgWidget.updateCurve(link.getRepresentation(), x1, y1, x2, y2);
          }
        });
      }, this);

      node.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", node);
      }, this);
    },

    __addNode: function(node) {
      let nodeBase = new qxapp.components.workbench.NodeBase();
      nodeBase.setMetadata(node);
      this.__addNodeToWorkbench(nodeBase);

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
    },

    __addLink: function(node1, node2) {
      const pointList = this.__getLinkPoints(node1, node2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__SvgWidget.drawCurve(x1, y1, x2, y2);
      let linkBase = new qxapp.components.workbench.LinkBase(linkRepresentation);
      linkBase.setInputNodeId(node1.getNodeId());
      linkBase.setOutputNodeId(node2.getNodeId());
      node1.addOutputLinkID(linkBase.getLinkId());
      node2.addInputLinkID(linkBase.getLinkId());
      this.__Links.push(linkBase);

      linkBase.getRepresentation().node.addEventListener("click", function(e) {
        console.log("clicked", linkBase.getLinkId(), e);
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
      for (let i = 0; i < this.__Nodes.length; i++) {
        if (this.__Nodes[i].getNodeId() === id) {
          return this.__Nodes[i];
        }
      }
      return null;
    },

    __getLink: function(id) {
      for (let i = 0; i < this.__Links.length; i++) {
        if (this.__Links[i].getLinkId() === id) {
          return this.__Links[i];
        }
      }
      return null;
    },

    _serializePipelineDataStructure: function() {
      let pipeline = {};
      for (let i = 0; i < this.__Nodes.length; i++) {
        const nodeId = this.__Nodes[i].getNodeId();
        pipeline[nodeId] = {};
        pipeline[nodeId].serviceId = this.__Nodes[i].getMetadata().id;
        pipeline[nodeId].input = this.__Nodes[i].getMetadata().input;
        pipeline[nodeId].output = this.__Nodes[i].getMetadata().output;
        pipeline[nodeId].settings = this.__Nodes[i].getMetadata().settings;
        pipeline[nodeId].children = [];
        for (let j = 0; j < this.__Links.length; j++) {
          if (nodeId === this.__Links[j].getInputNodeId()) {
            pipeline[nodeId].children.push(this.__Links[j].getOutputNodeId());
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

    __getProducers: function() {
      const producers = [{
        "id": "modeler",
        "name": "Modeler",
        "input": [],
        "output": [{
          "name": "Scene",
          "type": "scene",
          "value": ""
        }],
        "settings": [{
          "name": "ViPModel",
          "options": [
            "Rat",
            "Sphere"
          ],
          "text": "Select ViP Model",
          "type": "select",
          "value": 0
        }],
        "viewer": {
          "port": null
        }
      },
      {
        "id": "NumberGeneratorID",
        "name": "Number Generator",
        "input": [],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [{
          "name": "number",
          "text": "Number",
          "type": "number",
          "value": 0
        }]
      }];
      return this.__createMenuFromList(producers);
    },

    __getComputationals: function() {
      const computationals = [{
        "id": "ColleenClancy",
        "name": "Colleen Clancy - dummy",
        "input": [
          {
            "name": "NaValue",
            "type": "number",
            "value": 10
          },
          {
            "name": "KrValue",
            "type": "number",
            "value": 10
          },
          {
            "name": "BCLValue",
            "type": "number",
            "value": 10
          },
          {
            "name": "beatsValue",
            "type": "number",
            "value": 10
          },
          {
            "name": "LigandValue",
            "type": "number",
            "value": 10
          },
          {
            "name": "cAMKIIValue",
            "type": "number",
            "value": 10
          }
        ],
        "output": [
          {
            "name": "outputFolder",
            "type": "folder",
            "value": "url"
          },
          {
            "name": "Allresults",
            "order": [
              "t",
              "I_Ca_store",
              "Ito",
              "Itof",
              "Itos",
              "INa",
              "IK1",
              "s1",
              "k1",
              "Jserca",
              "Iks",
              "Jleak",
              "ICFTR",
              "Incx"
            ],
            "type": "csv"
          }
        ],
        "settings": [
          {
            "name": "NaValue",
            "text": "Na blocker drug concentration",
            "type": "number",
            "value": 10
          },
          {
            "name": "KrValue",
            "text": "Kr blocker drug concentration",
            "type": "number",
            "value": 10
          },
          {
            "name": "BCLValue",
            "text": "Basic cycle length (BCL)",
            "type": "number",
            "value": 10
          },
          {
            "name": "beatsValue",
            "text": "Number of beats",
            "type": "number",
            "value": 10
          },
          {
            "name": "LigandValue",
            "text": "Ligand concentration",
            "type": "number",
            "value": 10
          },
          {
            "name": "cAMKIIValue",
            "options": [
              "A",
              "B",
              "C",
              "D"
            ],
            "text": "Adjust cAMKII activity level",
            "type": "select",
            "value": 0
          }
        ]
      },
      {
        "id": "Computational2",
        "name": "Computational 2",
        "input": [{
          "name": "Scene",
          "type": "scene",
          "value": ""
        }],
        "output": [{
          "name": "Other numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      },
      {
        "id": "Computational3",
        "name": "Computational 3",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Some numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      },
      {
        "id": "Computational4",
        "name": "Computational 4",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Other numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      }];
      return this.__createMenuFromList(computationals);
    },

    __getAnalyses: function() {
      const analyses = [{
        "id": "jupyter-base-notebook",
        "name": "Jupyter",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [],
        "settings": [],
        "viewer": {
          "port": null
        }
      },
      {
        "id": "Analysis2",
        "name": "Analysis 2",
        "input": [{
          "name": "Number",
          "type": "scene",
          "value": ""
        }],
        "output": [],
        "settings": []
      }];
      return this.__createMenuFromList(analyses);
    }
  }
});
