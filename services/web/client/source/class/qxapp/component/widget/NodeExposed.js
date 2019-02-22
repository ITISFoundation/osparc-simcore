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
 * Widget that represents what nodes need to be exposed to outside the container.
 *
 * It offers Drag&Drop mechanism for exposing inner nodes.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutput = new qxapp.component.widget.NodeExposed(node);
 *   nodeOutput.populateNodeLayout();
 *   this.getRoot().add(nodeOutput);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodeExposed", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base();

    let nodeExposedLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeExposedLayout);

    this.set({
      decorator: "main"
    });

    let atom = new qx.ui.basic.Atom().set({
      rich: true,
      center: true,
      draggable: true,
      droppable: true
    });
    atom.getChildControl("label").set({
      textAlign: "center"
    });
    node.bind("label", atom, "label", {
      converter: function(data) {
        return data + "'s<br>outputs";
      }
    });

    this._add(atom, {
      flex: 1
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
      this.__createUIPorts(true, metaData.inputs);
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
    }
  }
});
