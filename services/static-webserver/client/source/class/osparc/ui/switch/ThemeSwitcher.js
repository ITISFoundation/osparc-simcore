/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Switch button for controlling the theme
 */

qx.Class.define("osparc.ui.switch.ThemeSwitcher", {
  type: "static",

  statics: {
    getValidThemes: function() {
      return Object.values(qx.Theme.getAll()).filter(theme => theme.type === "meta");
    },

    isSwitchUseful: function() {
      const validThemes = this.getValidThemes();
      if (validThemes && validThemes.length === 2) {
        return true;
      }
      return false;
    },

    switchTheme: function() {
      const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
      if (validThemes.length !== 2) {
        return;
      }

      const currentTheme = qx.theme.manager.Meta.getInstance().getTheme();
      const idx = validThemes.findIndex(validTheme => validTheme.name === currentTheme.name);
      if (idx !== -1) {
        const theme = validThemes[1-idx];
        osparc.Preferences.getInstance().setThemeName(theme.name);
        osparc.Preferences.getInstance().saveThemeName(theme.name);
      }
    },

    bindIconToTheme: function(widget, buttonImageSize) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => {
        osparc.ui.switch.ThemeSwitcher.updateIcon(widget, buttonImageSize);
      }, this);
      osparc.ui.switch.ThemeSwitcher.updateIcon(widget, buttonImageSize);
    },

    updateIcon: function(widget, buttonImageSize) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      const theme = themeManager.getTheme();
      const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
      const idx = validThemes.findIndex(validTheme => validTheme.name === theme.name);
      widget.setIcon(idx === 0 ? "@FontAwesome5Solid/toggle-on/"+buttonImageSize : "@FontAwesome5Solid/toggle-off/"+buttonImageSize);
    }
  }
});
