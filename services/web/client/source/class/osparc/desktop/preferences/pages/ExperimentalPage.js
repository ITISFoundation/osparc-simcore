/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Experimental Misc in preferences dialog
 *
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.ExperimentalPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/flask/24";
    const title = this.tr("Experimental");
    this.base(arguments, title, iconSrc);

    const themeSelector = this.__createThemesSelector();
    if (themeSelector) {
      this.add(themeSelector);
    }

    const experimentalSettings = this.__createExperimentalSettings();
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

      const linkBtn = new osparc.ui.form.LinkButton(this.tr("To qx-osparc-theme"), "https://github.com/ITISFoundation/qx-osparc-theme");
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

    __createExperimentalSettings: function() {
      // layout
      const box = this._createSectionBox("Experimental preferences");

      const label = this._createHelpLabel(this.tr(
        "This is a list of experimental preferences"
      ));
      box.add(label);

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();

      const cbAutoPorts = new qx.ui.form.CheckBox(this.tr("Connect ports automatically"));
      preferencesSettings.bind("autoConnectPorts", cbAutoPorts, "value");
      cbAutoPorts.bind("value", preferencesSettings, "autoConnectPorts");
      box.add(cbAutoPorts);

      const cbAutoOpenNode = new qx.ui.form.CheckBox(this.tr("Open node automatically when opening studies with a single node"));
      preferencesSettings.bind("autoOpenNode", cbAutoOpenNode, "value");
      cbAutoOpenNode.bind("value", preferencesSettings, "autoOpenNode");
      box.add(cbAutoOpenNode);

      return box;
    }
  }
});
