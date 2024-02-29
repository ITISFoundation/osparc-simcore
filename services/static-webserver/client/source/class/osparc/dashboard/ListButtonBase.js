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
      minHeight: osparc.dashboard.ListButtonBase.ITEM_HEIGHT,
      allowGrowX: true
    });

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(10);
    layout.setColumnFlex(osparc.dashboard.ListButtonBase.POS.DESCRIPTION, 1);
    this._setLayout(layout);
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
      UPDATES: 4,
      UI_MODE: 5,
      TAGS: 6,
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
      let titleRow;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail(null, 40, this.self().ITEM_HEIGHT-2*5).set({
            minHeight: 40,
            minWidth: 40
          });
          control.getChildControl("image").set({
            anonymous: true,
            decorator: "rounded"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.THUMBNAIL
          });
          break;
        }
        case "title-row":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true,
            allowGrowX: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TITLE
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
            alignY: "middle",
            maxWidth: 300,
            allowGrowX: true,
            rich: true,
          });
          titleRow = this.getChildControl("title-row");
          titleRow.addAt(control, 0, {
            flex: 1
          });
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            rich: true,
            maxHeight: 16,
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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6)).set({
            anonymous: true
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.STATUS
          });
          break;
        case "project-status-icon":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            textColor: "status_icon",
            height: 12,
            width: 12,
            padding: 1
          });
          titleRow = this.getChildControl("project-status");
          titleRow.addAt(control, 0);
          break;
        case "project-status-label":
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: false
          });
          titleRow = this.getChildControl("project-status");
          titleRow.addAt(control, 1, {
            flex: 1
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
