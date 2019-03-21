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
  extend: qxapp.component.widget.NodeInOut,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments, node);

    let atom = this.base().getChildren()[0];
    this.getNode().bind("label", atom, "label");
  },

  members: {
    populateNodeLayout: function() {
      this.emptyPorts();

      const metaData = this.getNode().getMetaData();
      this._createUIPorts(false, metaData.outputs);
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
