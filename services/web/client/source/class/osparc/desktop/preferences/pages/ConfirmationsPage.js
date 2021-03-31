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

/**
 * Confirmations in preferences dialog
 */

qx.Class.define("osparc.desktop.preferences.pages.ConfirmationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/question-circle/24";
    const title = this.tr("Confirmations");
    this.base(arguments, title, iconSrc);

    const experimentalSettings = this.__createConfirmationsSettings();
    this.add(experimentalSettings);
  },

  members: {
    __createThemesSelector: function() {
      let validThemes = {};
      const themes = qx.Theme.getAll();
      for (const key in themes) {
        const theme = themes[key];
        if (theme.type === "meta") {
          validThemes[key] = theme;
        }
      }
      if (Object.keys(validThemes).length === 1) {
        return null;
      }

      // layout
      const box = this._createSectionBox("UI Theme");

      const label = this._createHelpLabel(this.tr(
        "This is a list of experimental themes for the UI. By default the \
         osparc-theme is selected"
      ));
      box.add(label);

      const linkBtn = new osparc.ui.form.LinkButton(this.tr("To qx-osparc-theme"), null, "https://github.com/ITISFoundation/qx-osparc-theme");
      box.add(linkBtn);

      const select = new qx.ui.form.SelectBox("Theme");
      box.add(select);

      // fill w/ themes
      const themeMgr = qx.theme.manager.Meta.getInstance();
      const currentTheme = themeMgr.getTheme();

      for (const key in themes) {
        const theme = themes[key];
        if (theme.type === "meta") {
          const item = new qx.ui.form.ListItem(theme.name);
          item.setUserData("theme", theme.name);
          select.add(item);
          if (theme.name == currentTheme.name) {
            select.setSelection([item]);
          }
        }
      }

      select.addListener("changeSelection", evt => {
        const selected = evt.getData()[0].getUserData("theme");
        const theme = qx.Theme.getByName(selected);
        if (theme) {
          themeMgr.setTheme(theme);
        }
      });
      return box;
    },

    __createConfirmationsSettings: function() {
      // layout
      const box = this._createSectionBox("Confirmations preferences");

      const label = this._createHelpLabel(this.tr(
        "This is a list of Confirmations asked throughout the application that can be enabled/disabled"
      ));
      box.add(label);

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();

      const cbConfirmDeleteNode = new qx.ui.form.CheckBox(this.tr("Delete Node"));
      preferencesSettings.bind("confirmDeleteNode", cbConfirmDeleteNode, "value");
      cbConfirmDeleteNode.bind("value", preferencesSettings, "confirmDeleteNode");
      box.add(cbConfirmDeleteNode);

      return box;
    }
  }
});
