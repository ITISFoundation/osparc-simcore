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

    const staticsLayout = this.__createStaticsLayout();
    this.add(staticsLayout);
  },

  members: {
    __createStaticsLayout: function() {
      // layout
      const box = this._createSectionBox("Statics settings");

      const label = this._createHelpLabel(this.tr(
        "This is a list of the 'statics' resources"
      ));
      box.add(label);

      osparc.data.Resources.get("statics")
        .then(statics => {
          console.log("statics", statics);

          const form = new qx.ui.form.Form();
          for (let [key, value] of Object.entries(statics)) {
            const textField = new qx.ui.form.TextField().set({
              value: typeof value === "object" ? JSON.stringify(value) : value.toString(),
              readOnly: true
            });
            form.add(textField, key, null, key);
          }
          box.add(new qx.ui.form.renderer.Single(form));
        });

      return box;
    }
  }
});
