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
 *   let nodeOutput = new qxapp.component.widget.NodeOutput(node);
 *   nodeOutput.populateNodeLayout();
 *   this.getRoot().add(nodeOutput);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodeOutput", {
  extend: qxapp.component.widget.NodeInOut,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments, node);

    const atom = this.getAtom();
    this.getNode().bind("label", atom, "label", {
      converter: function(data) {
        return data + "'s<br>outputs";
      }
    });
  },

  members: {
    populateNodeLayout: function() {
      this.emptyPorts();

      const metaData = this.getNode().getMetaData();
      this._createUIPorts(true, metaData.inputs);
    }
  }
});
