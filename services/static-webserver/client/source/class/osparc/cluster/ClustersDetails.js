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

qx.Class.define("osparc.cluster.ClustersDetails", {
  extend: qx.ui.core.Widget,

  construct: function(selectClusterId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    if (selectClusterId === undefined) {
      selectClusterId = 0;
    }
    this.__clusterId = selectClusterId;
    this.__populateClustersLayout();
    this.__addClusterWorkersLayout();
    this.__startFetchingDetails();
  },

  members: {
    __clustersSelectBox: null,
    __clusterId: null,
    __clusterWorkers: null,

    __populateClustersLayout: function() {
      const clustersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

      const clustersLabel = new qx.ui.basic.Label(this.tr("Connected clusters"));
      clustersLayout.add(clustersLabel);

      const selectBox = this.__clustersSelectBox = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      osparc.cluster.Utils.populateClustersSelectBox(selectBox);
      selectBox.addListener("changeSelection", e => {
        const clusterId = e.getData()[0].id;
        this.__selectedClusterChanged(clusterId);
      }, this);
      clustersLayout.add(selectBox);

      clustersLayout.add(new qx.ui.core.Spacer(10, null));

      const clusterStatusLabel = new qx.ui.basic.Label(this.tr("Status:"));
      clustersLayout.add(clusterStatusLabel);

      const clusterStatus = this.__clusterStatus = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/lightbulb/16"
      });
      clustersLayout.add(clusterStatus);

      this._add(clustersLayout);

      selectBox.getSelectables().forEach(selectable => {
        if (selectable.id === this.__clusterId) {
          selectBox.setSelection([selectable]);
        }
      });
    },

    __addClusterWorkersLayout: function() {
      const clusterWorkers = this.__clusterWorkers = new osparc.cluster.ClusterWorkers();
      this._add(clusterWorkers, {
        flex: 1
      });
    },

    __selectedClusterChanged: function(clusterId) {
      osparc.cluster.Utils.getInstance().stopFetchingDetails(this.__clusterId);
      this.__clusterId = clusterId;
      this.__startFetchingDetails();
    },

    __startFetchingDetails: function() {
      const clusters = osparc.cluster.Utils.getInstance();
      clusters.addListener("clusterDetailsReceived", e => {
        const data = e.getData();
        if (this.__clusterId === data.clusterId) {
          this.__clusterStatus.setTextColor("error" in data ? "failed-red" : "ready-green");
          this.__clusterWorkers.populateWorkersDetails("error" in data ? null : data.clusterDetails);
        }
      });
      clusters.startFetchingDetails(this.__clusterId);
    }
  },

  destruct: function() {
    osparc.cluster.Utils.getInstance().stopFetchingDetails(this.__clusterId);
  }
});
