/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that represents the output of an input node.
 * It creates a VBox with widgets representing each of the output ports of the node.
 * It can also create widget for representing default inputs (isInputModel = false).
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodePorts = new osparc.component.widget.NodePorts(node, isInputModel);
 *   this.getRoot().add(nodePorts);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodePorts", {
  extend: osparc.desktop.PanelView,
  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   * @param isInputModel {Boolean} false for representing defaultInputs
   */
  construct: function(node, isInputModel = true) {
    this.setIsInputModel(isInputModel);
    this.setNode(node);

    this._setLayout(new qx.ui.layout.Grow());

    this.base(arguments, node.getLabel());

    this.getTitleBar().set({
      height: 30
    });
    node.bind("label", this, "title");

    node.getStatus().bind("output", this.getChildControl("icon"), "source", {
      converter: output => {
        switch (output) {
          case "up-to-date":
            return osparc.utils.StatusUI.getIconSource("up-to-date");
          case "out-of-date":
            return osparc.utils.StatusUI.getIconSource("modified");
          case "busy":
            return osparc.utils.StatusUI.getIconSource("running");
          case "not-available":
          default:
            return osparc.utils.StatusUI.getIconSource();
        }
      },
      onUpdate: (source, target) => {
        if (source.getOutput() === "busy") {
          target.getContentElement().addClass("rotate");
        } else {
          target.getContentElement().removeClass("rotate");
        }
      }
    }, this);
    node.getStatus().bind("output", this.getChildControl("icon"), "textColor", {
      converter: output => osparc.utils.StatusUI.getColor(output)
    }, this);
    node.getStatus().bind("output", this.getChildControl("icon"), "toolTipText", {
      converter: output => {
        switch (output) {
          case "up-to-date":
            return this.tr("Ready");
          case "out-of-date":
            return this.tr("Out of date");
          case "busy":
            return this.tr("Not ready yet");
          case "not-available":
          default:
            return "";
        }
      }
    }, this);
  },

  properties: {
    isInputModel: {
      check: "Boolean",
      init: true,
      nullable: false
    },

    node: {
      check: "osparc.data.model.Node",
      nullable: false
    }
  },

  members: {

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    getMetaData: function() {
      return this.getNode().getMetaData();
    },

    populatePortsData: function() {
      const metaData = this.getNode().getMetaData();
      if (this.getIsInputModel()) {
        this.__createUIPorts(metaData.outputs);
      }
    },

    __createUIPorts: function(ports) {
      // Always create ports if node is a container
      if (!this.getNode().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      const portTree = new osparc.component.widget.inputs.NodeOutputTree(this.getNode(), ports);
      this.setContent(portTree);
    }
  }
});
