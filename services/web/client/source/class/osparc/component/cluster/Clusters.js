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

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__populateClusters();
  },

  members: {
    __populateClusters: function() {
      this._removeAll();

      osparc.data.Resources.get("clusters")
        .then(clusters => {
          // Workaround: insert default cluster: 0
          if (!(clusters.includes(0))) {
            clusters.unshift({
              id: 0
            });
          }
          clusters.forEach(cluster => {
            this.__populateClusterDetails(cluster.id);
          });
        });
    },

    __populateClusterDetails: function(clusterId) {
      const clusterDetailsView = new osparc.component.cluster.ClusterDetails(clusterId);
      this._add(clusterDetailsView);
    }
  }
});
