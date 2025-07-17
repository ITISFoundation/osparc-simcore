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
 *   let workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
 *   this.getRoot().add(workbenchUIPreview);
 * </pre>
 */

qx.Class.define("osparc.workbench.WorkbenchUIPreview2", {
  extend: osparc.workbench.WorkbenchUI,

  construct: function(wbData, wbDataUi) {
    this.base(arguments);

    this.set({
      backgroundColor: "background-main"
    });

    this.__wbData = wbData || {};
    this.__wbDataUi = wbDataUi || {};

    this.__buildPreview();
  },

  members: {
    __wbData: null,
    __wbDataUi: null,

    // overridden
    _addItemsToLayout: function() {
      this._addWorkbenchLayer();
    },

    // overridden
    _loadModel: function() {
      return; // no model to load, this is a preview
    },

    // overridden
    _addEventListeners: function() {
      this.addListenerOnce("appear", this._listenToMouseWheel, this);
    },

    __buildPreview: function() {
      this._clearAll();
      this.resetSelection();

      // create nodes
      const nodes = this.__wbData.nodes || {};
      Object.entries(nodes).forEach(([nodeId, nodeData]) => {
        // we assume that the metadata was fetched before
        const serviceMetadata = osparc.store.Services.getMetadata(nodeData["key"], nodeData["version"]);
        const node = osparc.data.model.Node(null, serviceMetadata, nodeId);
        const nodeUI = new osparc.workbench.NodeUI(node);
        nodeUI.setIsMovable(false);
        this._addNodeUIToWorkbench(nodeUI, node.position);
      });
      qx.ui.core.queue.Layout.flush();

      // create edges
      const edges = this.__wbData.edges || {};
      for (const edgeId in edges) {
        const edge = edges[edgeId];
        this._createEdge(edge.from, edge.to, edgeId);
      }
    },
  }
});
