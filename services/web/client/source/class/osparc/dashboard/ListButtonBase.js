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
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      allowGrowX: true
    });

    this._setLayout(new qx.ui.layout.HBox(10));
  },

  statics: {
    ITEM_WIDTH: 600,
    ITEM_HEIGHT: 40,
    SPACING: 5,
    POS: {
      THUMBNAIL: 0,
      LOCK_STATUS: 1,
      TITLE: 2,
      DESCRIPTION: 3,
      TAGS: 4,
      PERMISSION: 5,
      SHARED: 6,
      LAST_CHANGE: 7,
      TSR: 8,
      UI_MODE: 9,
      UPDATE_STUDY: 10,
      OPTIONS: 11
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail(null, 40, this.self().ITEM_HEIGHT-2*5).set({
            minWidth: 40
          });
          control.getChildControl("image").set({
            anonymous: true
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.THUMBNAIL);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "title-14",
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.TITLE);
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            minWidth: 100,
            font: "text-14",
            alignY: "middle",
            allowGrowX: true
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.DESCRIPTION, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyIcon: function(value, old) {
      if (value.includes("@FontAwesome5Solid/")) {
        value += "24";
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
      const label = this.getChildControl("description");
      label.setValue(value);
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
