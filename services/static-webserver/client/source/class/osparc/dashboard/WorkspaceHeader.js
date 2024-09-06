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

    const layout = new qx.ui.layout.HBox(10);
    this._setLayout(layout);

    this.set({
      minHeight: this.self().HEIGHT,
      maxHeight: this.self().HEIGHT,
      height: this.self().HEIGHT,
      alignY: "middle"
    })
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
        case "thumbnail":
          control = new osparc.ui.basic.Thumbnail(null, this.self().HEIGHT * 2, this.self().HEIGHT);
          control.getChildControl("image").set({
            anonymous: true,
            alignY: "middle",
            alignX: "center",
            allowGrowX: true,
            allowGrowY: true
          });
          control.getContentElement().setStyles({
            "border-radius": "6px"
          });
          this._add(control);
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            allowGrowY: true,
            alignY: "middle",
          });
          this._add(control);
          break;
        case "subtitle-md":
          control = new osparc.ui.markdown.Markdown().set({
            font: "text-13",
            noMargin: true,
            maxHeight: 18,
            alignY: "middle",
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function(workspaceId) {
      const image = this.getChildControl("thumbnail").getChildControl("image");
      const title = this.getChildControl("title");
      const description = this.getChildControl("subtitle-md");

      const workspace = osparc.store.Workspaces.getWorkspace(workspaceId);
      if (workspace) {
        const thumbnail = workspace.getThumbnail();
        if (thumbnail) {
          this.getChildControl("thumbnail").getContentElement().setStyles({
            "background-image": `url(${thumbnail})`,
            "background-repeat": "no-repeat",
            "background-size": "cover", // auto width, 85% height
            "background-position": "center center",
            "background-origin": "border-box"
          });
          image.set({
            visibility: "excluded",
          });
        } else {
          image.set({
            source: osparc.store.Workspaces.iconPath(32),
            visibility: "visible",
          });
        }

        workspace.bind("name", title, "value");
        workspace.bind("description", description, "value");
      } else {
        image.setSource("@FontAwesome5Solid/home/30");
        title.setValue(this.tr("My Workspace"));
      }
    }
  }
});
