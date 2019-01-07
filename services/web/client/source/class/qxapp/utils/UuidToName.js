/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.utils.UuidToName", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    project: {
      check: "qxapp.data.model.Project",
      nullable: true
    }
  },

  members: {
    convertToName: function(itemUuid) {
      if (this.isPropertyInitialized("project")) {
        const prj = this.getProject();
        if (itemUuid === prj.getUuid()) {
          return prj.getName();
        }
        const wrkb = prj.getWorkbench();
        const allNodes = wrkb.getNodes(true);
        for (const nodeId in allNodes) {
          const node = allNodes[nodeId];
          if (itemUuid === node.getNodeId()) {
            return node.getLabel();
          }
        }
      }
      return itemUuid;
    }
  }
});
