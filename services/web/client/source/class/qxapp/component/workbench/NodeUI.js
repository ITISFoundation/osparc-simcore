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

/**
 * Window that is used to represent a node in the WorkbenchUI.
 *
 * It implements Drag&Drop mechanism to provide internode connections.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeUI = new qxapp.component.workbench.NodeUI(node);
 *   nodeUI.populateNodeLayout();
 *   workbench.add(nodeUI)
 * </pre>
 */

const nodeWidth = 180;
const portHeight = 16;

qx.Class.define("qxapp.component.workbench.NodeUI", {
  extend: qx.ui.window.Window,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
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
      width: nodeWidth,
      maxWidth: nodeWidth,
      minWidth: nodeWidth,
      contentPadding: 0
    });

    this.setNode(node);

    this.__createNodeLayout();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },
    thumbnail: {
      check: "String",
      nullable: true,
      apply: "_applyThumbnail"
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

    __createNodeLayout: function() {
      this.setLayout(new qx.ui.layout.VBox(5));

      if (this.getNode().getThumbnail()) {
        this.setThumbnail(this.getNode().getThumbnail());
      }

      let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this.add(inputsOutputsLayout, {
        flex: 1
      });

      let inputsBox = new qx.ui.layout.VBox(5);
      this.__inputPortLayout = new qx.ui.container.Composite(inputsBox).set({
        marginLeft: 4
      });
      inputsOutputsLayout.add(this.__inputPortLayout, {
        width: "50%"
      });

      let outputsBox = new qx.ui.layout.VBox(5);
      this.__outputPortLayout = new qx.ui.container.Composite(outputsBox).set({
        marginRight: 4
      });
      inputsOutputsLayout.add(this.__outputPortLayout, {
        width: "50%"
      });

      this.__progressBar = new qx.ui.indicator.ProgressBar().set({
        height: 10,
        margin: [0, 4, 4, 4]
      });
      this.add(this.__progressBar);
    },

    populateNodeLayout: function() {
      const node = this.getNode();
      node.bind("label", this, "caption");
      if (node.isContainer()) {
        this.setIcon("@FontAwesome5Solid/folder-open/14");
      }
      this.__inputPort = null;
      this.__outputPort = null;
      const metaData = node.getMetaData();
      if (metaData) {
        this.__createUIPorts(true, metaData.inputs);
        this.__createUIPorts(false, metaData.outputs);
      }
      node.bind("progress", this.__progressBar, "value");
    },

    getInputPort: function() {
      return this.__inputPort;
    },

    getOutputPort: function() {
      return this.__outputPort;
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
        this.__inputPort = label;
        this.__inputPortLayout.add(label.ui);
      } else {
        this.__outputPort = label;
        this.__outputPortLayout.add(label.ui);
      }
    },

    __createUIPort: function(isInput) {
      const labelText = (isInput) ? "in" : "out";
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
      const bounds = this.getCurrentBounds();
      const captionHeight = 20; // Otherwise is changing and misplacing the links
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width;
      let y = bounds.top + captionHeight + portHeight/2 + 2;
      if (this.getThumbnail()) {
        y += this.getThumbnail().getBounds().height;
      }
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
    },

    _applyThumbnail: function(thumbnail, oldThumbnail) {
      if (oldThumbnail !== null) {
        this.removeAt(0);
      }
      this.addAt(new qx.ui.embed.Html(thumbnail).set({
        height: 100,
        cssClass: "no-user-select"
      }), 0);
    }
  }
});
