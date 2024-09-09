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
    },
    accessRights: {
      check: "Object",
      nullable: false,
      init: {},
      event: "changeAccessRights",
      apply: "__applyAccessRights"
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
          control = new osparc.ui.basic.Thumbnail(null, this.self().HEIGHT, this.self().HEIGHT);
          control.getChildControl("image").set({
            anonymous: true,
            alignY: "middle",
            alignX: "center",
            allowGrowX: true,
            allowGrowY: true
          });
          control.getContentElement().setStyles({
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
        case "share-layout":
          this.__addSpacer();
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "share-icon": {
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            allowGrowX: false,
            allowShrinkX: false
          });
          const layout = this.getChildControl("share-layout");
          layout.addAt(control, 0);
          break;
        }
        case "share-text": {
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          const layout = this.getChildControl("share-layout");
          layout.addAt(control, 1);
        }
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function(workspaceId) {
      this.getChildControl("icon");
      const title = this.getChildControl("title");

      const workspace = osparc.store.Workspaces.getWorkspace(workspaceId);
      if (workspaceId === -1) {
        this.__setIcon(osparc.store.Workspaces.iconPath(32));
        title.setValue(this.tr("Shared Workspaces"));
        this.resetAccessRights();
      } else if (workspace) {
        const thumbnail = workspace.getThumbnail();
        this.__setIcon(thumbnail ? thumbnail : osparc.store.Workspaces.iconPath(32));
        workspace.bind("name", title, "value");
        workspace.bind("accessRights", this, "accessRights");
      } else {
        this.__setIcon("@FontAwesome5Solid/home/30");
        title.setValue(this.tr("My Workspace"));
        this.resetAccessRights();
      }
    },

    __addSpacer: function() {
      const spacer = new qx.ui.basic.Label("-").set({
        font: "text-16",
        alignY: "middle",
      });
      this._add(spacer);
    },

    __setIcon: function(source) {
      const icon = this.getChildControl("icon");
      const image = icon.getChildControl("image");
      image.resetSource();
      icon.getContentElement().setStyles({
        "background-image": "none"
      });

      if (source.includes("@")) {
        image.set({
          source
        });
      } else {
        icon.getContentElement().setStyles({
          "background-image": `url(${source})`,
          "background-repeat": "no-repeat",
          "background-size": "cover",
          "background-position": "center center",
          "background-origin": "border-box"
        });
      }
    },

    __applyAccessRights: function(value) {
      const shareIcon = this.getChildControl("share-icon");
      const shareText = this.getChildControl("share-text");
      if (value && Object.keys(value).length) {
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, value);
        shareText.setValue(Object.keys(value).length + " members");
        shareIcon.show();
        shareText.show();
      } else {
        shareIcon.exclude();
        shareText.exclude();
      }
    },
  }
});
