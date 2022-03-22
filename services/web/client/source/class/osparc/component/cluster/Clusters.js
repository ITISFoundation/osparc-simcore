/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.cluster.Clusters", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const grid = new qx.ui.layout.Grid(10, 6);
    grid.setColumnFlex(1, 1);
    const clusterGrid = this.__clustersGrid = new qx.ui.container.Composite(grid);
    this._add(clusterGrid);

    this.__populateClusters();
  },

  members: {
    __populateClusters: function() {
      const clusterGrid = this.__clustersGrid;
      clusterGrid.removeAll();

      osparc.data.Resources.get("clusters")
        .then(clusters => {
          clusters.forEach((cluster, idx) => {
            this.__populateClusterEntry(cluster, idx);
          });
        });
    },

    __populateClusterEntry: function(cluster, idx) {
      const clusterGrid = this.__clustersGrid;
      const label = new qx.ui.basic.Label(cluster.name);
      clusterGrid.add(label, {
        row: idx,
        column: 0
      });
    }
  }
});
