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

/**
 * Widget used for displaying a Workspace information
 *
 */

qx.Class.define("osparc.dashboard.WorkspaceHeader", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    this.set({
      minHeight: this.self().HEIGHT,
      maxHeight: this.self().HEIGHT,
      height: this.self().HEIGHT,
      alignY: "middle",
    });
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId",
      apply: "__buildLayout"
    }
  },

  statics: {
    HEIGHT: 36
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new osparc.ui.basic.Thumbnail(null, this.self().HEIGHT, this.self().HEIGHT).set({
            minHeight: this.self().HEIGHT,
            minWidth: this.self().HEIGHT
          });
          control.getChildControl("image").getContentElement().setStyles({
            "border-radius": "4px"
          });
          this._add(control);
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            alignY: "middle",
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function(workspaceId) {
      const icon = this.getChildControl("icon");
      const title = this.getChildControl("title");

      const workspace = osparc.store.Workspaces.getWorkspace(workspaceId);
      if (workspace) {
        const thumbnail = workspace.getThumbnail();
        icon.setSource(thumbnail ? thumbnail : osparc.store.Workspaces.iconPath(32));
        workspace.bind("name", title, "value");
      } else {
        icon.setSource("@FontAwesome5Solid/home/30");
        title.setValue(this.tr("My Workspace"));
      }
    }
  }
});
