/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton for trying to convert a (file) uuid into a human readable text.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let image = osparc.utils.Avatar.getUrl(userEmail);
 * </pre>
 */

qx.Class.define("osparc.utils.UuidToName", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true
    }
  },

  members: {
    convertToName: function(itemUuid) {
      if (this.isPropertyInitialized("study")) {
        const prj = this.getStudy();
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
