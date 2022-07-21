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

    const byHitsBtn = new qx.ui.form.ToggleButton(null, this.self().NUMERIC_ICON_DOWN+iconSize);
    byHitsBtn.sortBy = "hits";
    const byNameBtn = new qx.ui.form.ToggleButton(null, this.self().ALPHA_ICON_DOWN+iconSize);
    byNameBtn.sortBy = "name";
    const sortByGroup = new qx.ui.form.RadioGroup().set({
      allowEmptySelection: false
    });
    [
      byHitsBtn,
      byNameBtn
    ].forEach(btn => {
      this._add(btn);
      sortByGroup.add(btn);
      btn.getContentElement().setStyles({
        "border-radius": "8px"
      });
    });
    sortByGroup.addListener("changeSelection", () => {
      const sortBy = sortByGroup.getSelection()[0].sortBy;
      this.fireDataEvent("sortBy", sortBy);
    });
  },

  events: {
    "sortBy": "qx.event.type.Data" // "hits" or "name"
  },

  statics: {
    NUMERIC_ICON_DOWN: "@FontAwesome5Solid/sort-numeric-down/",
    NUMERIC_ICON_UP: "@FontAwesome5Solid/sort-numeric-up/",
    ALPHA_ICON_DOWN: "@FontAwesome5Solid/sort-alpha-down/",
    ALPHA_ICON_UP: "@FontAwesome5Solid/sort-alpha-up/"
  },

  members: {
    __iconSize: null
  }
});
