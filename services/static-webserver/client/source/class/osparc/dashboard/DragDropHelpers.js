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
    moveStudy: {
      dragStart: function(event, studyDataOrigin, studyItem) {
        event.addAction("move");
        event.addType("osparc-moveStudy");
        event.addData("osparc-moveStudy", {
          "studyDataOrigin": studyDataOrigin,
        });

        // init drag indicator
        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.getChildControl("dragged-resource").set({
          label: studyDataOrigin["name"],
          icon: "@FontAwesome5Solid/file/16",
        });
        dragWidget.start();

        // make it semi transparent while being dragged
        studyItem.setOpacity(0.2);
      },

      dragOver: function(event, folderItem, workspaceDestId) {
        let compatible = false;
        const studyDataOrigin = event.getData("osparc-moveStudy")["studyDataOrigin"];
        const workspaceIdOrigin = studyDataOrigin["workspaceId"];
        const workspaceOrigin = osparc.store.Workspaces.getInstance().getWorkspace(workspaceIdOrigin);
        const workspaceDest = osparc.store.Workspaces.getInstance().getWorkspace(workspaceDestId);
        // Compatibility checks:
        // - Drag over "Shared Workspaces" (0)
        //   - No
        // - My Workspace -> My Workspace (1)
        //   - Yes
        // - My Workspace -> Shared Workspace (2)
        //   - Delete on Study
        //   - Write on dest Workspace
        // - Shared Workspace -> My Workspace (3)
        //   - Delete on origin Workspace
        // - Shared Workspace -> Shared Workspace (4)
        //   - Delete on origin Workspace
        //   - Write on dest Workspace
        if (workspaceDestId === -1) { // (0)
          compatible = false;
        } else if (workspaceIdOrigin === null && workspaceDestId === null) { // (1)
          compatible = true;
        } else if (workspaceIdOrigin === null && workspaceDest) { // (2)
          compatible = osparc.data.model.Study.canIDelete(studyDataOrigin["accessRights"]) && workspaceDest.getMyAccessRights()["write"];
        } else if (workspaceOrigin && workspaceDestId === null) { // (3)
          compatible = workspaceOrigin.getMyAccessRights()["delete"];
        } else if (workspaceOrigin && workspaceDest) { // (4)
          compatible = workspaceOrigin.getMyAccessRights()["delete"] && workspaceDest.getMyAccessRights()["write"];
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
        const studyData = event.getData("osparc-moveStudy")["studyDataOrigin"];
        const studyToFolderData = {
          studyData,
          destFolderId: folderDest.getFolderId(),
        };
        return studyToFolderData;
      },
    },

    moveFolder: {
      dragStart: function(event, folderOrigin, folderItem) {
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

        // make it semi transparent while being dragged
        folderItem.setOpacity(0.2);
      },

      dragOver: function(event, folderItem, folderDest) {
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

    dragLeave: function(item) {
      item.getChildControl("icon").resetTextColor();
      const dragWidget = osparc.dashboard.DragWidget.getInstance();
      dragWidget.setDropAllowed(false);
    },

    dragEnd: function(draggedItem) {
      // bring back opacity after drag
      draggedItem.setOpacity(1);

      // hide drag indicator
      const dragWidget = osparc.dashboard.DragWidget.getInstance();
      dragWidget.end();
    }
  }
});
