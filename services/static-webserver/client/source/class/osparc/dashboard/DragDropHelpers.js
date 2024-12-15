/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.DragDropHelpers", {
  type: "static",

  statics: {
    moveFolder: {
      dragStart: function(event, folderOrigin) {
        event.addAction("move");
        event.addType("osparc-moveFolder");
        event.addData("osparc-moveFolder", {
          "folderOrigin": folderOrigin,
        });

        // init drag indicator
        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.getChildControl("dragged-resource").set({
          label: folderOrigin.getName(),
          icon: "@FontAwesome5Solid/folder/16",
        });
        dragWidget.start();
      },

      dragOver: function(event, folderDest, folderItem) {
        let compatible = false;
        // Compatibility checks:
        // - It's not the same folder
        // - My workspace
        //   - None
        // - Shared workspace
        //   - write access on workspace
        const folderOrigin = event.getData("osparc-moveFolder")["folderOrigin"];
        compatible = folderDest !== folderOrigin;
        const workspaceId = folderOrigin.getWorkspaceId();
        if (compatible) {
          if (workspaceId) {
            const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
            if (workspace) {
              compatible = workspace.getMyAccessRights()["write"];
            }
          } else {
            compatible = true;
          }
        }

        if (compatible) {
          folderItem.getChildControl("icon").setTextColor("strong-main");
        } else {
          folderItem.getChildControl("icon").setTextColor("danger-red");
          // do not allow
          event.preventDefault();
        }

        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.setDropAllowed(compatible);
      },

      drop: function(event, folderDest) {
        const folderOrigin = event.getData("osparc-moveFolder")["folderOrigin"];
        const folderToFolderData = {
          folderId: folderOrigin.getFolderId(),
          destFolderId: folderDest.getFolderId(),
        };
        return folderToFolderData;
      },
    },

    dragEnd: function() {
      // hide drag indicator
      const dragWidget = osparc.dashboard.DragWidget.getInstance();
      dragWidget.end();
    }
  }
});
