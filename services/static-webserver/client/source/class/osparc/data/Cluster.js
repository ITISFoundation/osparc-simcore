/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.data.Cluster", {
  extend: qx.core.Object,

  construct: function(clusterData) {
    this.base(arguments);

    this.set({
      clusterId: clusterData["cluster_id"],
      name: clusterData["name"],
      status: clusterData["status"],
      nWorkers: clusterData["n_workers"],
    });
  },

  properties: {
    clusterId: {
      check: "String",
      nullable: false,
      init: null,
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
    },

    status: {
      check: "String",
      nullable: false,
      init: null,
    },

    nWorkers: {
      check: "Number",
      init: 0,
      nullable: true,
    },
  },
});
