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

    this.__populateClustersLayout(selectClusterId);
  },

  members: {
    __clustersSelectBox: null,
    __clusterDetails: null,

    __populateClustersLayout: function(selectClusterId) {
      const clustersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

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

      clustersLayout.add(new qx.ui.core.Spacer(10, null));

      const clusterStatusLabel = new qx.ui.basic.Label(this.tr("Status:"));
      clustersLayout.add(clusterStatusLabel);

      const clusterStatusBulb = this.__clusterStatusBulb = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/lightbulb/16"
      });
      clustersLayout.add(clusterStatusBulb);

      this._add(clustersLayout);

      if (selectClusterId === undefined) {
        selectClusterId = 0;
      }
      selectBox.getSelectables().forEach(selectable => {
        if (selectable.id === selectClusterId) {
          selectBox.setSelection([selectable]);
        }
      });
      this.__updateClusterDetails(selectClusterId);

      this.__clusterDetails.bind("clusterStatus", clusterStatusBulb, "textColor", {
        converter: status => {
          if (status === "connected") {
            return "ready-green";
          } else if (status === "failed") {
            return "failed-red";
          }
          return "text";
        }
      });
    },

    __updateClusterDetails: function(clusterId) {
      if (this._getChildren().includes(this.__clusterDetails)) {
        this._remove(this.__clusterDetails);
        this.__clusterDetails.dispose();
      }
      const clusterDetails = this.__clusterDetails = new osparc.component.cluster.ClusterWorkers(clusterId);
      this._add(clusterDetails, {
        flex: 1
      });
    }
  }
});
