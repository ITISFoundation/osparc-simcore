/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.dashboard.SideSearch", {
  extend: qx.ui.tabview.TabView,
  construct: function() {
    this.base(arguments);
    this.add(this.__classifiersFilter());
  },
  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },
  members: {
    __classifiersFilter: function() {
      const classifiersPage = new qx.ui.tabview.Page(this.tr("Classifiers")).set({
        appearance: "dashboard-page",
        layout: new qx.ui.layout.Grow()
      });
      classifiersPage.add(new osparc.component.filter.TreeFilter("classifiers", "dashboardClassifiers"));
      classifiersPage.getChildControl("button").setFont("text-16");
      return classifiersPage;
    }
  }
});
