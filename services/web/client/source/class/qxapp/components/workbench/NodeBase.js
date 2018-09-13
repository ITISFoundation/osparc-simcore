const nodeWidth = 240;
const portHeight = 16;

qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function(nodeImageId, uuid) {
    this.base();

    this.set({
      appearance: "window-small-cap",
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      minWidth: nodeWidth,
      maxWidth: nodeWidth,
      // custom
      nodeImageId: nodeImageId,
      nodeId: uuid || qxapp.utils.Utils.uuidv4()
    });
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    },

    nodeImageId: {
      check: "String",
      nullable: false
    },

    propsWidget: {
      check: "qxapp.components.form.renderer.PropForm"
    },

    viewerButton: {
      init: null,
      check: "qx.ui.form.Button"
    }
  },

  events: {
    "LinkDragStart": "qx.event.type.Data",
    "LinkDragOver": "qx.event.type.Data",
    "LinkDrop": "qx.event.type.Data",
    "LinkDragEnd": "qx.event.type.Data",
    "NodeMoving": "qx.event.type.Event",
    "ShowViewer": "qx.event.type.Data"
  },

  members: {
    __inputPorts: null,
    __outputPorts: null,
    __inputPortsUI: null,
    __outputPortsUI: null,
    __progressLabel: null,
    __settingsForm: null,
    __progressBar: null,
    __metaData: null,

    getMetaData: function() {
      return this.__metaData;
    },

    createNodeLayout: function(nodeData) {
      let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
      this.setLayout(nodeLayout);

      let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this.add(inputsOutputsLayout, {
        flex: 1
      });

      let inputsBox = new qx.ui.layout.VBox(5);
      this.__inputPortsUI = new qx.ui.container.Composite(inputsBox);
      inputsOutputsLayout.add(this.__inputPortsUI, {
        width: "50%"
      });

      let outputsBox = new qx.ui.layout.VBox(5);
      this.__outputPortsUI = new qx.ui.container.Composite(outputsBox);
      inputsOutputsLayout.add(this.__outputPortsUI, {
        width: "50%"
      });


      let progressBox = new qx.ui.container.Composite(new qx.ui.layout.Basic());
      progressBox.setMinWidth(nodeWidth-20);

      this.__progressBar = new qx.ui.indicator.ProgressBar();
      this.__progressBar.setWidth(nodeWidth-20);
      progressBox.add(this.__progressBar, {
        top: 0,
        left: 0
      });

      this.__progressLabel = new qx.ui.basic.Label("0%");
      progressBox.add(this.__progressLabel, {
        top: 3,
        left: nodeWidth/2 - 20
      });

      this.add(progressBox);

      const nodeImageId = this.getNodeImageId();
      let store = qxapp.data.Store.getInstance();
      let metaData = store.getNodeMetaDataFromCache(nodeImageId);
      if (metaData) {
        this.__populateNode(metaData, nodeData);
      } else {
        console.error("Invalid ImageID - Not populating "+nodeImageId);
      }
    },

    getInputPorts: function() {
      return this.__inputPorts;
    },
    getInputPort: function(portId) {
      return this.__inputPorts[portId];
    },
    getOutputPorts: function() {
      return this.__outputPorts;
    },
    getOutputPort: function(portId) {
      return this.__outputPorts[portId];
    },

    getInputValues: function() {
      return this.getPropsWidget().getValues();
    },

    // override qx.ui.window.Window "move" event listener
    _onMovePointerMove: function(e) {
      this.base(arguments, e);
      if (e.getPropagationStopped() === true) {
        this.fireEvent("NodeMoving");
      }
    },

    __getCurrentBounds: function() {
      let bounds = this.getBounds();
      let cel = this.getContentElement();
      if (cel) {
        let domeEle = cel.getDomElement();
        if (domeEle) {
          bounds.left = parseInt(domeEle.style.left);
          bounds.top = parseInt(domeEle.style.top);
        }
      }
      // NavigationBar height must be subtracted
      // bounds.left = this.getContentLocation().left;
      // bounds.top = this.getContentLocation().top;
      return bounds;
    },

    __populateNode: function(metaData, nodeData) {
      this.__metaData = metaData;
      // this.__creteSettings(metaData.inputs);
      this.setCaption(metaData.name + " " + metaData.version);
      this.__createViewerButton();
      this.__outputPorts = {};
      this.__inputPorts = {};
      this.__createPorts("Input", metaData.inputs);
      this.__createPorts("Output", metaData.outputs);
      this.__addSettings(metaData.inputs);
      if (nodeData) {
        this.__settingsForm.setData(nodeData.inputs);
      }
    },

    __addSettings: function(inputs) {
      if (inputs === null) {
        return;
      }
      let form = this.__settingsForm = new qxapp.components.form.Auto(inputs);
      // FIXME
      // this.__settingsForm.addListener("changeData", function(e) {
      //  let settingsForm = e.getData();
      //  for (var settingKey in settingsForm) {
      //    if (this.__metaData.inputs) {
      //      for (let i=0; i<this.__metaData.inputs.length; i++) {
      //        if (settingKey === this.__metaData.inputs[i].key) {
      //          this.__metaData.inputs[i].value = settingsForm[settingKey];
      //        }
      //      }
      //    }
      //  }
      // }, this);
      this.setPropsWidget(new qxapp.components.form.renderer.PropForm(form));
    },

    __createViewerButton: function() {
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
              let button = new qx.ui.form.Button("Open Viewer");
              let entryPoint = "";
              if (entryPointD) {
                entryPoint = "/" + entryPointD;
              }
              const srvUrl = "http://" + window.location.hostname + ":" + publishedPort + entryPoint;
              this.set({
                viewerButton: button
              });
              button.addListener("execute", function(e) {
                this.fireDataEvent("ShowViewer", {
                  url: srvUrl,
                  name: metaData.name,
                  nodeId: this.getNodeId()
                });
              }, this);
              console.debug(metaData.name, "Service ready on " + srvUrl);
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

    __createPorts: function(type, ports) {
      if (!ports) {
        return;
      }
      Object.keys(ports).sort((a, b) => {
        let x = ports[a].displayOrder;
        let y = ports[b].displayOrder;
        if (x > y) {
          return 1;
        }
        if (x < y) {
          return -1;
        }
        return 0;
      })
        .forEach(portId => {
          switch (type) {
            case "Output":
              this.__addOutputPort(portId, ports[portId]);
              break;
            case "Input":
              this.__addInputPort(portId, ports[portId]);
              break;
          }
        });
    },
    __addInputPort: function(portId, inputData) {
      let label = this.__createPort(true, portId, inputData);
      this.getInputPorts()[portId] = label;
      this.__inputPortsUI.add(label.ui);
    },

    __addOutputPort: function(portId, outputData) {
      let label = this.__createPort(false, portId, outputData);
      this.getOutputPorts()[portId]=label;
      this.__outputPortsUI.add(label.ui);
    },
    __createPort: function(isInput, portId, portData) {
      let label = {};
      label.portId = portId;
      label.isInput = isInput;
      label.portType = portData.type;
      let iconSize = (portHeight-4).toString();
      let icon = "@FontAwesome5Solid/edit/" + iconSize;
      if (portData.type.match(/^data:/)) {
        icon = "@FontAwesome5Solid/file/" + (portHeight-2).toString();
      }
      const alignX = (isInput) ? "left" : "right";
      label.ui = new qx.ui.basic.Atom(portData.label, icon).set({
        height: portHeight,
        draggable: true,
        droppable: true,
        iconPosition: alignX,
        alignX: alignX,
        allowGrowX: false
      });
      label.ui.portId = portId;

      var tooltip = new qx.ui.tooltip.ToolTip(portData.description, icon);
      tooltip.setShowTimeout(50);
      label.ui.setToolTip(tooltip);

      [
        ["dragstart", "LinkDragStart"],
        ["dragover", "LinkDragOver"],
        ["drop", "LinkDrop"],
        ["dragend", "LinkDragEnd"]
      ].forEach(eventPair => {
        label.ui.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeId(),
            portId: portId,
            isInput: isInput,
            dataType: portData.type
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
      return label;
    },

    getLinkPoint: function(port) {
      const nodeBounds = this.__getCurrentBounds();
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      const captionHeight = this.__childControls.captionbar.getBounds().height;
      const inputOutputs = this.getChildren()[0];
      const inputPorts = inputOutputs.getChildren()[0].getChildren();
      const outputPorts = inputOutputs.getChildren()[1].getChildren();
      const ports = inputPorts.concat(outputPorts);
      let portBounds;
      for (let i=0; i<ports.length; i++) {
        if (port.portId === ports[i].portId) {
          portBounds = ports[i].getBounds();
          break;
        }
      }
      let y = nodeBounds.top + captionHeight + 10 + portBounds.top + portBounds.height/2;
      return [x, y];
    },

    setProgress: function(progress) {
      this.__progressLabel.setValue(progress + "%");
      this.__progressBar.setValue(progress);
    },

    getProgress: function() {
      return this.__progressBar.getValue();
    }
  }
});
