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

  members: {
    // overriden
    _addItemsToLayout: function() {
      this._addWorkbenchLayer();
    },

    // overriden
    _addWorkbenchLayer: function() {
      const workbenchLayer = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      this._add(workbenchLayer, {
        flex: 1
      });

      const workbenchLayoutScroll = this._workbenchLayoutScroll = new qx.ui.container.Scroll();
      const workbenchLayout = this._workbenchLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      workbenchLayoutScroll.add(workbenchLayout);
      workbenchLayer.add(workbenchLayoutScroll, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });

      const desktop = this._addDesktop(workbenchLayout);
      this._addSVGLayer(desktop);
    },

    _loadModel: function(model) {
      this.clearAll();
      this.resetSelectedNodes();
      this._currentModel = model;

      // create nodes
      let nodes = model.getNodes();
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

      this.setScale(0.25);
    }
  }
});
