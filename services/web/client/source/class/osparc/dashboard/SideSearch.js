/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.dashboard.SideSearch", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 10,
      marginTop: 20
    });

    this.__buildLayout();
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  members: {
    __buildLayout: function() {
      const title = new qx.ui.basic.Label(this.tr("Classifiers")).set({
        font: "title-14"
      });
      this._add(title);

      const classifier = new osparc.component.filter.ClassifiersFilter("classifiers", "studyBrowser");
      this._add(classifier, {
        flex: 1
      });
    }
  }
});
