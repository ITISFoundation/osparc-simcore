/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Tester Misc in preferences dialog
 */

qx.Class.define("osparc.desktop.preferences.pages.TesterPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

    const statics = this.__createStaticsLayout();
    container.add(statics);

    const localStorage = this.__createLocalStorageLayout();
    container.add(localStorage);

    const scroll = new qx.ui.container.Scroll(container);
    this._add(scroll, {
      flex: 1
    });
  },

  members: {
    __createStaticsLayout: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Statics"));

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr(
        "This is a list of the 'statics' resources"
      ));
      box.add(label);

      const statics = osparc.store.Store.getInstance().get("statics");
      const form = new qx.ui.form.Form();
      for (let [key, value] of Object.entries(statics)) {
        const textField = new qx.ui.form.TextField().set({
          value: typeof value === "object" ? JSON.stringify(value) : value.toString(),
          readOnly: true
        });
        form.add(textField, key, null, key);
      }
      box.add(new qx.ui.form.renderer.Single(form));

      return box;
    },

    __createLocalStorageLayout: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Local Storage"));

      const items = {
        ...window.localStorage
      };
      const form = new qx.ui.form.Form();
      for (let [key, value] of Object.entries(items)) {
        const textField = new qx.ui.form.TextField().set({
          value: typeof value === "object" ? JSON.stringify(value) : value.toString(),
          readOnly: true
        });
        form.add(textField, key, null, key);
      }
      box.add(new qx.ui.form.renderer.Single(form));

      return box;
    }
  }
});
