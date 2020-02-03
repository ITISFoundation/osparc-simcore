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

    this.__populateInput();
  },

  members: {
    __populateInput: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const nodeUILayoutBig = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      nodeUILayoutBig.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      const nodeUILayout = this.__createFakeNodeUI();
      nodeUILayoutBig.add(nodeUILayout);
      nodeUILayoutBig.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this._add(nodeUILayoutBig, {
        flex: 1
      });
    },

    __createFakeNodeUI: function() {
      const node = this.getNode();

      const nodeUILayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        height: 80,
        backgroundColor: "node-background",
        draggable: true,
        droppable: true
      });

      const header = new qx.ui.basic.Label().set({
        font: "text-13",
        textColor: "#DCDCDC",
        textAlign: "left",
        height: 18,
        padding: 3
      });
      node.bind("label", header, "value");
      const outPort = new qx.ui.basic.Label(this.tr("out")).set({
        font: "text-13",
        textColor: "#BABABA",
        allowGrowX: true,
        textAlign: "right",
        padding: 5
      });
      const progressBar = new qx.ui.indicator.ProgressBar().set({
        height: 10,
        margin: 3
      });
      node.bind("label", progressBar, "value");

      nodeUILayout.add(header);
      nodeUILayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      nodeUILayout.add(outPort);
      nodeUILayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      nodeUILayout.add(progressBar);

      return nodeUILayout;
    },

    populateNodeLayout: function() {
      this._populateNodeLayout(false);
    }
  }
});
