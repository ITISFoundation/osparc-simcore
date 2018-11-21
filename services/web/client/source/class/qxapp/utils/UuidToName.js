qx.Class.define("qxapp.utils.UuidToName", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    projectModel: {
      check: "qxapp.data.model.ProjectModel",
      nullable: true
    }
  },

  members: {
    convertToName: function(itemUuid) {
      if (this.isPropertyInitialized("projectModel")) {
        const prj = this.getProjectModel();
        if (itemUuid === prj.getUuid()) {
          return prj.getName();
        }
        const wrkb = prj.getWorkbenchModel();
        const allNodes = wrkb.getNodeModels(true);
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
