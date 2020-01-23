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
 * Widget that represents an input node in a container.
 *
 * It offers Drag&Drop mechanism for connecting input nodes to inner nodes.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeInput = new osparc.component.widget.NodeInput(node);
 *   nodeInput.populateNodeLayout();
 *   this.getRoot().add(nodeInput);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeInput", {
  extend: osparc.component.widget.NodeInOut,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments, node);
  },

  members: {
    populateNodeLayout: function() {
      this.emptyPorts();

      const metaData = this.getNode().getMetaData();
      this._createUIPorts(false, metaData.outputs);
    }
  }
});
