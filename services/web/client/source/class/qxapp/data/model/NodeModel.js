qx.Class.define("qxapp.data.model.NodeModel", {
  extend: qx.core.Object,

  construct: function(metaData, uuid) {
    this.base(arguments);

    this.__metaData = {};
    this.__innerNodes = {};
    this.__inputNodes = [];

    let nodeImageId = null;
    if (metaData && "key" in metaData) {
      // not container
      nodeImageId = metaData.key + "-" + metaData.version;
    }

    this.set({
      nodeImageId: nodeImageId,
      nodeId: uuid || qxapp.utils.Utils.uuidv4()
    });

    if (metaData) {
      this.__metaData = metaData;
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

    label: {
      check: "String",
      nullable: true
    },

    parentNodeId: {
      check: "String",
      nullable: true
    },

    propsWidget: {
      check: "qxapp.components.form.renderer.PropForm"
    },

    serviceUrl: {
      check: "String",
      nullable: true
    },

    viewerButton: {
      init: null,
      check: "qx.ui.form.Button"
    }
  },

  members: {
    __metaData: null,
    __innerNodes: null,
    __inputNodes: null,
    __settingsForm: null,
    __posX: null,
    __posY: null,

    isContainer: function() {
      return (this.getNodeImageId() === null);
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
        for (const innerNodeId in this.__innerNodes) {
          let myInnerNodes = this.__innerNodes[innerNodeId].getInnerNodes(true);
          innerNodes = Object.assign(innerNodes, myInnerNodes);
        }
      }
      return innerNodes;
    },

    addInnerNode: function(innerNodeId, innerNodeModel) {
      this.__innerNodes[innerNodeId] = innerNodeModel;
    },

    getInputNodes: function() {
      return this.__inputNodes;
    },

    populateNodeData: function(nodeData) {
      if (this.__metaData) {
        let metaData = this.__metaData;
        this.__startInteractiveNode();

        if (metaData && metaData.inputs) {
          this.__addSettings(metaData.inputs, nodeData);
        }

        if (nodeData && nodeData.position) {
          this.setPosition(nodeData.position.x, nodeData.position.y);
        }

        this.__inputNodes = [];
        if (nodeData && nodeData.inputNodes) {
          this.__inputNodes = nodeData.inputNodes;
        }

        const label = (nodeData && nodeData.label) ? nodeData.label : metaData.name;
        this.setLabel(label);
      }
    },

    __startInteractiveNode: function() {
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
              let button = new qx.ui.form.Button().set({
                icon: "@FontAwesome5Solid/play-circle/32"
              });
              this.set({
                viewerButton: button
              });
              button.addListener("execute", function(e) {
                this.fireDataEvent("ShowViewer", {
                  url: srvUrl,
                  name: this.getLabel(),
                  nodeId: this.getNodeId()
                });
              }, this);
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

    addInputNode: function(inputNodeId) {
      if (!this.__inputNodes.includes(inputNodeId)) {
        this.__inputNodes.push(inputNodeId);
      }
      // this.getPropsWidget().enableProp(link.getOutputPortId(), false);
    },

    removeLink: function(inputNodeId) {
      const index = this.__inputNodes.indexOf(inputNodeId);
      if (index > -1) {
        this.__inputNodes.splice(index, 1);
        return true;
      }
      // this.getPropsWidget().enableProp(link.getOutputPortId(), true);
      return false;
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
