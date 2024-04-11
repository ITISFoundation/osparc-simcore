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

qx.Class.define("osparc.ui.window.TabbedView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 20,
      paddingLeft: 10
    });

    this.getChildControl("tabs-view");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tabs-view":
          control = new qx.ui.tabview.TabView().set({
            barPosition: "left",
            contentPadding: 0
          });
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    addWidgetOnTopOfTheTabs: function(widget) {
      this.getChildControl("tabs-view").getChildControl("bar").add(widget);
    },

    __widgetToPage: function(title, iconSrc, widget) {
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      widget.set({
        margin: 10
      });
      page.add(widget, {
        flex: 1
      });
      return page;
    },

    addTab: function(title, iconSrc, widget) {
      const page = this.__widgetToPage(title, iconSrc, widget);
      this.getChildControl("tabs-view").add(page);
      return page;
    },

    _openPage: function(page) {
      if (page) {
        this.getChildControl("tabs-view").setSelection([page]);
        return true;
      }
      return false;
    },
  }
});
