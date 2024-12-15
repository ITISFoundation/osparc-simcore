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
    },

    dragEnd: function() {
      // hide drag indicator
      const dragWidget = osparc.dashboard.DragWidget.getInstance();
      dragWidget.end();
    }
  }
});
