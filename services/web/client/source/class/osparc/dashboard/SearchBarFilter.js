/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SearchBarFilter", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/search/16").set({
            backgroundColor: "transparent",
            paddingRight: 6,
            alignY: "middle",
            opacity: 0.5
          });
          this._add(control);
          break;
        case "text-field":
          control = new qx.ui.form.TextField().set({
            font: "text-16",
            placeholder: this.tr("search"),
            alignY: "bottom"
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "reset-button":
          control = new qx.ui.toolbar.Button(null, "@MaterialIcons/close/12").set({
            backgroundColor: "transparent",
            paddingLeft: 0,
            alignY: "middle",
            opacity: 0.7
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("search-icon");

      // const filterGroupId = "searchBarFilter";
      const textField = this.getChildControl("text-field");
      textField.addListener("changeValue", () => this.__filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);
    },

    __addTagFilter: function(filterGroupId) {
      const tagsFilter = this.__tagsFilter = new osparc.component.filter.UserTagsFilter("tags", filterGroupId).set({
        visibility: osparc.data.Permissions.getInstance().canDo("study.tag") ? "visible" : "excluded"
      });
      this._add(tagsFilter);
    },

    __resetFilters: function() {
      this.getChildControl("text-field").resetValue();
    },

    __filter: function() {
      console.log(this.getChildControl("text-field").getValue());
    }
  }
});
