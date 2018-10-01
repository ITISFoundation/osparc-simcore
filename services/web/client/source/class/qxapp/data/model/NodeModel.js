qx.Class.define("qxapp.data.model.NodeModel", {
  extend: qx.core.Object,

  construct: function(nodeData, uuid) {
    this.base(arguments);

    this.__metaData = {};
    this.__innerNodes = {};
    this.__connectedTo = [];

    let nodeImageId = nodeData.key;
    if (nodeData.key !== "container") {
      nodeImageId = nodeImageId + "-" + nodeData.version;
    }
    this.set({
      nodeImageId: nodeImageId || null,
      nodeId: uuid || qxapp.utils.Utils.uuidv4()
    });

    let store = qxapp.data.Store.getInstance();
    let metaData = store.getNodeMetaData(this.getNodeImageId());
    if (metaData) {
      this.__metaData = metaData;
    } else if (this.isContainer()) {
      this.__metaData.name = nodeData.name;
    } else {
      console.log("ImageID not found in registry - Not populating "+ this.getNodeImageId());
    }
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    },

    nodeImageId: {
      check: "String",
      nullable: true
    },

    serviceUrl: {
      check: "String",
      nullable: true
    },

    propsWidget: {
      check: "qxapp.components.form.renderer.PropForm"
    }
  },

  members: {
    __metaData: null,
    __innerNodes: null,
    __connectedTo: null,
    __settingsForm: null,
    __posX: null,
    __posY: null,

    isContainer: function() {
      let isContainer = false;
      isContainer = isContainer || (this.getNodeImageId() === "container"); // built Container
      isContainer = isContainer || (this.getMetaData().type === "container"); // container by default
      return isContainer;
    },

    getMetaData: function() {
      return this.__metaData;
    },

    getInputValues: function() {
      return this.getPropsWidget().getValues();
    },

    getInnerNodes: function(recursive = false) {
      let innerNodes = Object.assign({}, this.__innerNodes);
      if (recursive) {
        for (const innerNodeId of Object.keys(this.__innerNodes)) {
          let myInnerNodes = this.__innerNodes[innerNodeId].getInnerNodes(true);
          innerNodes = Object.assign(innerNodes, myInnerNodes);
        }
      }
      return innerNodes;
    },

    createInnerNodes: function(innerNodes) {
      for (const innerNodeId of Object.keys(innerNodes)) {
        let innerNodeMetaData = innerNodes[innerNodeId];
        let innerNode = new qxapp.data.model.NodeModel(innerNodeMetaData, innerNodeId);
        innerNode.populateNodeData(innerNodeMetaData);
        this.__innerNodes[innerNodeId] = innerNode;
      }
    },

    populateNodeData: function(nodeData) {
      if (this.__metaData) {
        let metaData = this.__metaData;
        this.__startNode();
        this.__addSettings(metaData.inputs, nodeData);

        if (nodeData && nodeData.position) {
          this.setPosition(nodeData.position.x, nodeData.position.y);
        }

        if (this.isContainer()) {
          if ("innerNodes" in nodeData) {
            this.createInnerNodes(nodeData.innerNodes);
          }
          if ("innerNodes" in metaData) {
            this.createInnerNodes(metaData.innerNodes);
          }
        }
      }
    },

    __startNode: function() {
      let metaData = this.__metaData;
      if (metaData.type == "dynamic") {
        const slotName = "startDynamic";
        let socket = qxapp.wrappers.WebSocket.getInstance();
        socket.on(slotName, function(val) {
          const {
            data,
            status
          } = val;
          if (status == 201) {
            const publishedPort = data["published_port"];
            const entryPointD = data["entry_point"];
            const nodeId = data["service_uuid"];
            if (nodeId !== this.getNodeId()) {
              return;
            }
            if (publishedPort) {
              const entryPoint = entryPointD ? ("/" + entryPointD) : "";
              const srvUrl = "http://" + window.location.hostname + ":" + publishedPort + entryPoint;
              this.setServiceUrl(srvUrl);
              console.log(metaData.name, "Service ready on " + srvUrl);
            }
          } else {
            console.error("Error starting dynamic service: ", data);
          }
        }, this);
        let data = {
          serviceKey: metaData.key,
          serviceVersion: metaData.version,
          nodeId: this.getNodeId()
        };
        socket.emit(slotName, data);
      }
    },

    __addSettings: function(inputs, nodeData) {
      if (inputs === null) {
        return;
      }
      let form = this.__settingsForm = new qxapp.components.form.Auto(inputs);
      this.setPropsWidget(new qxapp.components.form.renderer.PropForm(form));

      if (nodeData) {
        this.__settingsForm.setData(nodeData.inputs);
      }
    },

    addLink: function(link) {
      this.__connectedTo.push(link);
      this.getPropsWidget().enableProp(link.getOutputPortId(), false);
    },

    removeLink: function(link) {
      const index = this.__connectedTo.indexOf(link);
      if (index > -1) {
        this.__connectedTo.splice(index, 1);
      }
      this.getPropsWidget().enableProp(link.getOutputPortId(), true);
    },

    setPosition: function(x, y) {
      this.__posX = x;
      this.__posY = y;
    },

    getPosition: function() {
      return {
        x: this.__posX,
        y: this.__posY
      };
    }
  }
});
