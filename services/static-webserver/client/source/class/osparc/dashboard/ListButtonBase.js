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
      width: osparc.dashboard.ListButtonBase.ITEM_WIDTH,
      height: osparc.dashboard.ListButtonBase.ITEM_HEIGHT,
      allowGrowX: true
    });

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(10);
    layout.setColumnFlex(osparc.dashboard.ListButtonBase.POS.DESCRIPTION, 1);
    this._setLayout(layout);
  },

  statics: {
    ITEM_WIDTH: 600,
    ITEM_HEIGHT: 35,
    SPACING: 5,
    POS: {
      THUMBNAIL: 0,
      LOCK_STATUS: 1,
      TITLE: 2,
      DESCRIPTION: 3,
      TAGS: 4,
      PERMISSION: 5,
      SHARED: 6,
      TSR: 7,
      UI_MODE: 8,
      UPDATE_STUDY: 9,
      LAST_CHANGE: 10,
      HITS: 11,
      OPTIONS: 12
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail().set({
            maxImageWidth: 40,
            maxImageHeight: this.self().ITEM_HEIGHT-2*5,
            minImageWidth: 40
          });
          control.getChildControl("image").set({
            anonymous: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.THUMBNAIL
          });
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-15",
            alignY: "middle",
            rich: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TITLE
          });
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            rich: true,
            maxHeight: 15,
            minWidth: 100,
            font: "text-14",
            alignY: "middle",
            allowGrowX: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.DESCRIPTION
          });
          break;
        case "description-md":
          control = new osparc.ui.markdown.Markdown().set({
            maxHeight: 15,
            alignY: "middle",
            allowGrowX: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.DESCRIPTION
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
      const label = this.getChildControl("description-md");
      label.setValue(value);
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
