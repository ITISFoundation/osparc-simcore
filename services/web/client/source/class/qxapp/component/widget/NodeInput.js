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
 * Widget that represents an input node in a container.
 *
 * It offers Drag&Drop mechanism for connecting input nodes to inner nodes.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeInput = new qxapp.component.widget.NodeInput(node);
 *   nodeInput.populateNodeLayout();
 *   this.getRoot().add(nodeInput);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodeInput", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.setNode(node);

    this.base();

    let nodeInputLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeInputLayout);

    this.set({
      decorator: "main"
    });

    let atom = new qx.ui.basic.Atom().set({
      center: true,
      draggable: true,
      droppable: true
    });
    node.bind("label", atom, "label");
    const title16Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-16"]);
    atom.getChildControl("label").set({
      font: title16Font
    });

    this._add(atom, {
      flex: 1
    });
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
    "linkDragEnd": "qx.event.type.Data"
  },

  members: {
    __inputPort: null,
    __outputPort: null,

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    getMetaData: function() {
      return this.getNode().getMetaData();
    },

    populateNodeLayout: function() {
      const metaData = this.getNode().getMetaData();
      this.__inputPort = {};
      this.__outputPort = {};
      // this.__createUIPorts(true, metaData.inputs);
      this.__createUIPorts(false, metaData.outputs);
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
      this.__createUIPortConnections(this, isInput);
      let label = {
        isInput: isInput,
        ui: this
      };
      label.ui.isInput = isInput;
      if (isInput) {
        this.__inputPort["Input"] = label;
      } else {
        this.__outputPort["Output"] = label;
      }
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
      if (port.isInput === true) {
        console.log("Port should always be output");
        return null;
      }
      let nodeBounds = this.getCurrentBounds();
      if (nodeBounds === null) {
        // not rendered yet
        return null;
      }
      // It is always on the very left of the Desktop
      let x = 0;
      let y = nodeBounds.top + nodeBounds.height/2;
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
    }
  }
});
