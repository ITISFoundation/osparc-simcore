/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides three different ways for creating a new study
 * - Copy study with data
 *   - With a link
 *   - With a token
 * - Copy study without data, only the pipeline/workbench structure
 *   - By pasting the exported pipeline/workbench
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let newStudyDlg = new osparc.component.widget.newStudy.Dlg();
 *   this.getRoot().add(newStudyDlg);
 * </pre>
 */

qx.Class.define("osparc.component.widget.newStudy.Dlg", {
  extend: qx.ui.core.Widget,

  construct: function(template=null) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const tabView = new qx.ui.tabview.TabView();
    [
      [this.__getBasic, "Basic"],
      [this.__getWithWorkbench, "With pipeline"],
      [this.__getWithToken, "With pipeline and data"]
    ].forEach(pair => {
      const widget = pair[0].call(this, template);
      const page = new qx.ui.tabview.Page(pair[1]);
      page.setLayout(new qx.ui.layout.VBox());
      page.add(widget, {
        flex: 1
      });
      tabView.add(page);
    }, this);

    this._add(tabView, {
      flex: 1
    });
  },

  events: {
    "createStudy": "qx.event.type.Data",
    "autoloadStudy": "qx.event.type.Data"
  },

  members: {
    __getBasic: function(template) {
      const newBlankStudy = new osparc.component.widget.newStudy.Basic(template, false);
      newBlankStudy.addListener("createStudy", e => {
        this.fireDataEvent("createStudy", e.getData());
      }, this);
      return newBlankStudy;
    },

    __getWithWorkbench: function() {
      const newBlankStudy = new osparc.component.widget.newStudy.Basic(null, true);
      newBlankStudy.addListener("createStudy", e => {
        this.fireDataEvent("createStudy", e.getData());
      }, this);
      return newBlankStudy;
    },

    __getWithToken: function() {
      const newWithTokenStudy = new osparc.component.widget.newStudy.WithToken();
      newWithTokenStudy.addListener("autoloadStudy", e => {
        this.fireDataEvent("autoloadStudy", e.getData());
      }, this);
      return newWithTokenStudy;
    }
  }
});
