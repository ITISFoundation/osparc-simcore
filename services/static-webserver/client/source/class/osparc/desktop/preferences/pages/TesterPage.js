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
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/user-md/24";
    const title = this.tr("Tester");
    this.base(arguments, title, iconSrc);

    this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    const scroll = new qx.ui.container.Scroll(this.__container);

    this.__createStaticsLayout();
    this.__createLocalStorageLayout();

    this.add(scroll, {
      flex: 1
    });
  },

  members: {
    __createStaticsLayout: function() {
      // layout
      const box = this._createSectionBox(this.tr("Statics"));

      const label = this._createHelpLabel(this.tr(
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

      this.__container.add(box);
    },

    __createLocalStorageLayout: function() {
      // layout
      const box = this._createSectionBox(this.tr("Local Storage"));

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

      this.__container.add(box);
    }
  }
});
