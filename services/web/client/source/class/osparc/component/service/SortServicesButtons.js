/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (ignapas)

************************************************************************ */

qx.Class.define("osparc.component.service.SortServicesButtons", {
  extend: qx.ui.core.Widget,

  construct: function(iconSize = 14) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(4));
    this.set({
      marginRight: 8
    });

    this.__iconSize = iconSize;

    const hitsBtn = this.__hitsBtn = new qx.ui.form.ToggleButton().set({
      toolTipText: this.tr("Sort by Hits")
    });
    hitsBtn.sortBy = "hits";
    const nameBtn = this.__nameBtn = new qx.ui.form.ToggleButton().set({
      toolTipText: this.tr("Sort by Name")
    });
    nameBtn.sortBy = "name";
    [
      hitsBtn,
      nameBtn
    ].forEach(btn => {
      this._add(btn);
      btn.getContentElement().setStyles({
        "border-radius": "8px"
      });
      btn.addListener("tap", () => this.__btnExecuted(btn));
    });

    this.__hitsBtn.tristate = 1;
    this.__nameBtn.tristate = 0;
    this.__updateState();
  },

  events: {
    "sortBy": "qx.event.type.Data"
  },

  statics: {
    NUMERIC_ICON_DOWN: "@FontAwesome5Solid/sort-numeric-down/",
    NUMERIC_ICON_UP: "@FontAwesome5Solid/sort-numeric-up/",
    ALPHA_ICON_DOWN: "@FontAwesome5Solid/sort-alpha-down/",
    ALPHA_ICON_UP: "@FontAwesome5Solid/sort-alpha-up/",
    DefaultSorting: {
      "sort": "hits",
      "order": "down"
    }
  },

  members: {
    __iconSize: null,
    __hitsBtn: null,
    __nameBtn: null,

    __btnExecuted: function(btn) {
      if (btn === this.__hitsBtn) {
        this.__hitsBtn.tristate++;
        if (this.__hitsBtn.tristate === 3) {
          this.__hitsBtn.tristate = 1;
        }
        this.__nameBtn.tristate = 0;
      } else if (btn === this.__nameBtn) {
        this.__hitsBtn.tristate = 0;
        this.__nameBtn.tristate++;
        if (this.__nameBtn.tristate === 3) {
          this.__nameBtn.tristate = 1;
        }
      }
      this.__updateState();
      this.__announceSortChange();
    },

    __updateState: function() {
      switch (this.__hitsBtn.tristate) {
        case 0:
          this.__hitsBtn.set({
            value: false,
            icon: this.self().NUMERIC_ICON_DOWN+this.__iconSize
          });
          break;
        case 1:
          this.__hitsBtn.set({
            value: true,
            icon: this.self().NUMERIC_ICON_DOWN+this.__iconSize
          });
          break;
        case 2:
          this.__hitsBtn.set({
            value: true,
            icon: this.self().NUMERIC_ICON_UP+this.__iconSize
          });
          break;
      }

      switch (this.__nameBtn.tristate) {
        case 0:
          this.__nameBtn.set({
            value: false,
            icon: this.self().ALPHA_ICON_DOWN+this.__iconSize
          });
          break;
        case 1:
          this.__nameBtn.set({
            value: true,
            icon: this.self().ALPHA_ICON_DOWN+this.__iconSize
          });
          break;
        case 2:
          this.__nameBtn.set({
            value: true,
            icon: this.self().ALPHA_ICON_UP+this.__iconSize
          });
          break;
      }
    },

    __announceSortChange: function() {
      const data = {};
      if (this.__hitsBtn.tristate > 0) {
        data["sort"] = "hits";
        data["order"] = this.__hitsBtn.tristate === 1 ? "down" : "up";
      } else if (this.__nameBtn.tristate > 0) {
        data["sort"] = "name";
        data["order"] = this.__nameBtn.tristate === 1 ? "down" : "up";
      }
      this.fireDataEvent("sortBy", data);
    }
  }
});
