/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.ListButtonBase", {
  extend: osparc.dashboard.CardBase,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(10);
    layout.setColumnFlex(osparc.dashboard.ListButtonBase.POS.SPACER, 1);
    this._setLayout(layout);

    this.set({
      minHeight: osparc.dashboard.ListButtonBase.ITEM_HEIGHT,
      allowGrowX: true
    });

    this.getChildControl("spacer");
  },

  statics: {
    ITEM_HEIGHT: 35,
    SPACING: 5,
    POS: {
      THUMBNAIL: 0,
      LOCK_STATUS: 1,
      TITLE: 2,
      SPACER: 3,
      PROGRESS: 4,
      AVATAR_GROUP: 5,
      TAGS: 6,
      ICONS_LAYOUT: 7,
      OWNER: 8,
      SHARED: 9,
      LAST_CHANGE: 10,
      TSR: 11,
      HITS: 12,
      OPTIONS: 13,
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = osparc.dashboard.CardBase.createCardIcon();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.THUMBNAIL
          });
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
            alignY: "middle",
            maxWidth: 300,
            rich: true,
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TITLE
          });
          break;
        case "spacer":
          control = new qx.ui.core.Spacer();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.SPACER
          });
          break;
        case "owner":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            font: "text-12",
            alignY: "middle",
            allowGrowX: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.OWNER
          });
          break;
        case "icons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle"
          }))
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.ICONS_LAYOUT
          });
          break;
        case "project-status":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "text",
            height: 12,
            width: 12
          });
          this.getChildControl("icons-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyIcon: function(value, old) {
      if (value) {
        if (value.includes("@FontAwesome5Solid/")) {
          value += "22";
        }
        const image = this.getChildControl("icon").getChildControl("image");
        image.set({
          source: value
        });
        osparc.utils.Utils.setAltToImage(image, "card-icon");
      }
    },

    _applyThumbnail: function(value, old) {
      // do not shot thumbnail in list button, icon takes over
      return;
    },

    _applyTitle: function(value, old) {
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    _applyDescription: function(value, old) {
      return;
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
