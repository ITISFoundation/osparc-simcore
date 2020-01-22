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

    const atom = this.getAtom();
    let that = this;
    this.getNode().bind("label", atom, "label", {
      converter: function(nodeLabel) {
        let text = nodeLabel + "'s<br>outputs:";
        const outputLabels = that.__getOutputLabels(); // eslint-disable-line no-underscore-dangle
        for (let i=0; i<outputLabels.length; i++) {
          text += "<br> - " + outputLabels[i];
        }
        return text;
      }
    });
  },

  members: {
    populateNodeLayout: function() {
      this.emptyPorts();

      const metaData = this.getNode().getMetaData();
      this._createUIPorts(true, metaData.inputs);
    },

    __getOutputLabels: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const outputLabels = [];
      const outputNodes = this.getNode().getOutputNodes();
      for (let i=0; i<outputNodes.length; i++) {
        outputLabels.push(workbench.getNode(outputNodes[i]).getLabel());
      }
      return outputLabels;
    }
  }
});
