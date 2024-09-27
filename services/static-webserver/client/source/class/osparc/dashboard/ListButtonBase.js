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
    this.set({
      minHeight: osparc.dashboard.ListButtonBase.ITEM_HEIGHT,
      allowGrowX: true
    });

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(10);
    layout.setColumnFlex(osparc.dashboard.ListButtonBase.POS.TITLE, 1);
    this._setLayout(layout);
  },

  statics: {
    ITEM_HEIGHT: 40,
    SPACING: 5,
    POS: {
      THUMBNAIL: 0,
      LOCK_STATUS: 1,
      TITLE: 2,
      PROGRESS: 3,
      TAGS: 4,
      UPDATES: 5,
      UI_MODE: 6,
      STATUS: 7,
      PERMISSION: 8,
      TSR: 9,
      OWNER: 10,
      SHARED: 11,
      LAST_CHANGE: 12,
      HITS: 13,
      OPTIONS: 14
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail(null, 40, this.self().ITEM_HEIGHT-2*5).set({
            minHeight: 40,
            minWidth: 40
          });
          control.getChildControl("image").set({
            anonymous: true,
            decorator: "rounded",
          });
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
            allowGrowX: true,
            rich: true,
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TITLE
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
        case "project-status":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "status_icon",
            height: 12,
            width: 12
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.STATUS
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyIcon: function(value, old) {
      if (value.includes("@FontAwesome5Solid/")) {
        value += "22";
      }
      const image = this.getChildControl("icon").getChildControl("image");
      image.set({
        source: value
      });
    },

    _applyTitle: function(value, old) {
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    _applyDescription: function(value, old) {
      return
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
