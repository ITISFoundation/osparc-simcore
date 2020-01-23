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
 * Widget that represents what nodes need to be exposed to outside the container.
 *
 * It offers Drag&Drop mechanism for exposing inner nodes.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutput = new osparc.component.widget.NodeOutput(node);
 *   nodeOutput.populateNodeLayout();
 *   this.getRoot().add(nodeOutput);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeOutput", {
  extend: osparc.component.widget.NodeInOut,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments, node);

    this._getLayout().set({
      alignX: "center"
    });

    this.set({
      draggable: true,
      droppable: true
    });

    this._.add(new qx.ui.core.Spacer(), {
      flex: 1
    });

    const header = this.__getHeader();
    this.getNode().bind("label", header, "value", {
      converter: newLabel => {
        const headerTetx = newLabel + "'s<br>outputs:";
        return headerTetx;
      }
    });
    this._add(header);

    const outputs = this.__outputs = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.getNode().addListener("outputListChanged", () => {
      this.__populateOutputs();
    });
    this.__populateOutputs();
    this._add(outputs);

    this._add(new qx.ui.core.Spacer(), {
      flex: 1
    });
  },

  members: {
    __header: null,
    __outputs: null,

    __buildHeader: function() {
      const header = this.__header = new qx.ui.basic.Label().set({
        font: "title-16",
        textAlign: "center",
        rich: true
      });
      return header;
    },

    __getHeader: function() {
      if (this.__header === null) {
        return this.__buildHeader();
      }
      return this.__header;
    },

    __populateOutputs: function() {
      const outputs = this.__outputs;
      outputs.removeAll();
      const outputNodes = this.__getOutputNodes();
      outputNodes.forEach(outputNode => {
        const label = new qx.ui.basic.Label().set({
          textAlign: "center"
        });
        outputNode.bind("label", label, "value");
        outputs.add(label);
      });
      return outputs;
    },

    populateNodeLayout: function() {
      this.emptyPorts();

      const metaData = this.getNode().getMetaData();
      this._createUIPorts(true, metaData.inputs);
    },

    __getOutputNodes: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const outputNodes = [];
      const outputNodeIds = this.getNode().getOutputNodes();
      outputNodeIds.forEach(outputNodeId => {
        outputNodes.push(workbench.getNode(outputNodeId));
      });
      return outputNodes;
    }
  }
});
