/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

const nodeWidth = 180;
const portHeight = 16;

qx.Class.define("qxapp.component.workbench.NodeUI", {
  extend: qx.ui.window.Window,

  construct: function(node) {
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
      maxWidth: nodeWidth
    });

    this.setNode(node);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  events: {
    "linkDragStart": "qx.event.type.Data",
    "linkDragOver": "qx.event.type.Data",
    "linkDrop": "qx.event.type.Data",
    "linkDragEnd": "qx.event.type.Data",
    "nodeMoving": "qx.event.type.Event"
  },

  members: {
    __inputPortLayout: null,
    __outputPortLayout: null,
    __inputPort: null,
    __outputPort: null,
    __progressLabel: null,
    __progressBar: null,

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    getMetaData: function() {
      return this.getNode().getMetaData();
    },

    createNodeLayout: function() {
      let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
      this.setLayout(nodeLayout);

      let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this.add(inputsOutputsLayout, {
        flex: 1
      });

      let inputsBox = new qx.ui.layout.VBox(5);
      this.__inputPortLayout = new qx.ui.container.Composite(inputsBox);
      inputsOutputsLayout.add(this.__inputPortLayout, {
        width: "50%"
      });

      let outputsBox = new qx.ui.layout.VBox(5);
      this.__outputPortLayout = new qx.ui.container.Composite(outputsBox);
      inputsOutputsLayout.add(this.__outputPortLayout, {
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
    },

    populateNodeLayout: function() {
      const node = this.getNode();
      node.bind("label", this, "caption");
      if (node.isContainer()) {
        this.setIcon("@FontAwesome5Solid/folder-open/14");
      }
      this.__inputPort = {};
      this.__outputPort = {};
      const metaData = node.getMetaData();
      if (metaData) {
        this.__createUIPorts(true, metaData.inputs);
        this.__createUIPorts(false, metaData.outputs);
      }
      node.bind("progress", this.__progressLabel, "value", {
        converter: function(value) {
          return value + "%";
        }
      });
      node.bind("progress", this.__progressBar, "value");
    },

    getInputPort: function() {
      return this.__inputPort["Input"];
    },

    getOutputPort: function() {
      return this.__outputPort["Output"];
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNode().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      let portUI = this.__createUIPort(isInput);
      this.__createUIPortConnections(portUI, isInput);
      let label = {
        isInput: isInput,
        ui: portUI
      };
      label.ui.isInput = isInput;
      if (isInput) {
        this.__inputPort["Input"] = label;
        this.__inputPortLayout.add(label.ui);
      } else {
        this.__outputPort["Output"] = label;
        this.__outputPortLayout.add(label.ui);
      }
    },

    __createUIPort: function(isInput) {
      const labelText = (isInput) ? "Input(s)" : "Output(s)";
      const alignX = (isInput) ? "left" : "right";
      let uiPort = new qx.ui.basic.Atom(labelText).set({
        height: portHeight,
        draggable: true,
        droppable: true,
        alignX: alignX,
        allowGrowX: false
      });
      return uiPort;
    },

    __createUIPortConnections: function(uiPort, isInput) {
      [
        ["dragstart", "linkDragStart"],
        ["dragover", "linkDragOver"],
        ["drop", "linkDrop"],
        ["dragend", "linkDragEnd"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeId(),
            isInput: isInput
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    getLinkPoint: function(port) {
      let nodeBounds = this.getCurrentBounds();
      if (nodeBounds === null) {
        // not rendered yet
        return null;
      }
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      } else {
        // hack to place the arrow-head properly
        x -= 6;
      }

      const captionHeight = this.__childControls.captionbar.getBounds().height;
      const inputOutputs = this.getChildren()[0];
      let ports = null;
      if (port.isInput) {
        ports = inputOutputs.getChildren()[0].getChildren();
      } else {
        ports = inputOutputs.getChildren()[1].getChildren();
      }
      let portBounds;
      if (ports.length > 0) {
        portBounds = ports[0].getBounds();
      }
      let y = nodeBounds.top + captionHeight + 10 + portBounds.top + portBounds.height/2;
      return [x, y];
    },

    getCurrentBounds: function() {
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

    // override qx.ui.window.Window "move" event listener
    _onMovePointerMove: function(e) {
      this.base(arguments, e);
      if (e.getPropagationStopped() === true) {
        this.fireEvent("nodeMoving");
      }
    }
  }
});
