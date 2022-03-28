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

qx.Class.define("osparc.component.cluster.ClustersDetails", {
  extend: qx.ui.core.Widget,

  construct: function(selectClusterId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__populateClustersBox(selectClusterId);
  },

  members: {
    __clustersSelectBox: null,
    __clusterDetails: null,

    __populateClustersBox: function(selectClusterId) {
      const clustersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const clustersLabel = new qx.ui.basic.Label(this.tr("Connected clusters"));
      clustersLayout.add(clustersLabel);

      const selectBox = this.__clustersSelectBox = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      osparc.utils.Clusters.populateClustersSelectBox(selectBox);
      selectBox.addListener("changeSelection", e => {
        const clusterId = e.getData()[0].id;
        this.__updateClusterDetails(clusterId);
      }, this);
      clustersLayout.add(selectBox);

      this._add(clustersLayout);
      if (selectClusterId === undefined) {
        selectClusterId = 0;
      }
      selectBox.getSelectables().forEach(selectable => {
        if (selectable.id === selectClusterId) {
          selectBox.setSelection([selectable]);
        }
      });
    },

    __updateClusterDetails: function(clusterId) {
      if (this._getChildren().includes(this.__clusterDetails)) {
        this._remove(this.__clusterDetails);
        this.__clusterDetails.dispose();
      }
      const clusterDetailsView = this.__clusterDetails = new osparc.component.cluster.ClusterDetails(clusterId);
      this._add(clusterDetailsView, {
        flex: 1
      });
    }
  }
});
