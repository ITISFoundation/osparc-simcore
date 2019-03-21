/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Base class for NodeInput and NodeOutput
 */

qx.Class.define("qxapp.component.widget.NodeInOut", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.setNode(node);

    this.base();

    let nodeInOutLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeInOutLayout);

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
      font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-16"]),
      textAlign: "center"
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

    getInputPort: function() {
      return this.__inputPort;
    },

    getOutputPort: function() {
      return this.__outputPort;
    },

    emptyPorts: function() {
      this.__inputPort = null;
      this.__outputPort = null;
    },

    _createUIPorts: function(isInput, ports) {
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
        this.__inputPort = label;
      } else {
        this.__outputPort = label;
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
