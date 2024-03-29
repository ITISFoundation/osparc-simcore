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
        qx.event.message.Bus.getInstance().dispatchByName("themeSwitch", theme.name);
      }
    },

    bindLabelToTheme: function(widget, buttonImageSize) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => {
        osparc.ui.switch.ThemeSwitcher.updateLabel(widget, buttonImageSize);
      }, this);
      osparc.ui.switch.ThemeSwitcher.updateLabel(widget, buttonImageSize);
    },

    bindIconToTheme: function(widget, buttonImageSize) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => {
        osparc.ui.switch.ThemeSwitcher.updateIcon(widget, buttonImageSize);
      }, this);
      osparc.ui.switch.ThemeSwitcher.updateIcon(widget, buttonImageSize);
    },

    updateLabel: function(widget) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      const theme = themeManager.getTheme();
      const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
      const idx = validThemes.findIndex(validTheme => validTheme.name === theme.name);
      widget.setLabel(idx === 0 ? qx.locale.Manager.tr("Dark theme") : qx.locale.Manager.tr("Light theme"));
    },

    updateIcon: function(widget, buttonImageSize) {
      const themeManager = qx.theme.manager.Meta.getInstance();
      const theme = themeManager.getTheme();
      const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
      const idx = validThemes.findIndex(validTheme => validTheme.name === theme.name);
      widget.setIcon((idx === 0 ? "@FontAwesome5Solid/moon/" : "@FontAwesome5Solid/sun/") + buttonImageSize);
    }
  }
});
