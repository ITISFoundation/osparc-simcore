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


qx.Class.define("osparc.desktop.WorkbenchPanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    const toolbar = this.__toolbar = new osparc.desktop.WorkbenchToolbar();
    toolbar.set({
      margin: 5
    });
    toolbar.getChildControl("breadcrumb-navigation").exclude();
    toolbar.getContentElement().setStyles({
      "border-radius": "12px",
      "border": "1px solid " + qx.theme.manager.Color.getInstance().resolve("background-main")
    });
    this._add(toolbar);

    const workbenchUI = this.__workbenchUI = new osparc.component.workbench.WorkbenchUI();
    this._add(workbenchUI, {
      flex: 1
    });
  },

  members: {
    __toolbar: null,
    __workbenchUI: null,

    getMainView: function() {
      return this.__workbenchUI;
    },

    getToolbar: function() {
      return this.__toolbar;
    }
  }
});
