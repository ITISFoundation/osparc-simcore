/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @ignore(SVGElement)
 */

/**
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let workbenchUIPreview = new osparc.component.workbench.WorkbenchUIPreview();
 *   this.getRoot().add(workbenchUIPreview);
 * </pre>
 */

qx.Class.define("osparc.component.workbench.WorkbenchUIPreview", {
  extend: osparc.component.workbench.WorkbenchUI,

  construct: function() {
    this.base(arguments);

    this.set({
      backgroundColor: "background-main"
    });
  },

  members: {
    // overriden
    _addItemsToLayout: function() {
      this._addWorkbenchLayer();
      this._workbenchLayoutScroll.set({
        scrollbarX: "off",
        scrollbarY: "off"
      });
    },

    // overriden
    _loadModel: function(model) {
      this._clearAll();
      this.resetSelectedNodes();
      this._currentModel = model;
      if (model) {
        qx.ui.core.queue.Visibility.flush();

        // create nodes
        const nodes = model.getNodes();
        for (const nodeId in nodes) {
          const node = nodes[nodeId];
          const nodeUI = this._createNodeUI(nodeId);
          this._addNodeUIToWorkbench(nodeUI, node.getPosition());
        }

        // create edges
        for (const nodeId in nodes) {
          const node = nodes[nodeId];
          const inputNodeIDs = node.getInputNodes();
          inputNodeIDs.forEach(inputNodeId => {
            if (inputNodeId in nodes) {
              this._createEdgeBetweenNodes({
                nodeId: inputNodeId
              }, {
                nodeId: nodeId
              });
            }
          });
        }

        this.setScale(0.5);
      }
    },

    // overriden
    _addEventListeners: function() {
      return;
    }
  }
});
