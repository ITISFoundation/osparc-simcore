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
  extend: osparc.ui.basic.Switch,

  construct: function() {
    this.base(arguments);

    const validThemes = this.__validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.set({
      checked: qx.theme.manager.Meta.getInstance().getTheme().name === validThemes[1].name,
      toolTipText: this.tr("Switch theme")
    });

    this.addListener("changeChecked", () => {
      osparc.ui.switch.ThemeSwitcher.switchTheme();
    });
  },

  statics: {
    getValidThemes: function() {
      return Object.values(qx.Theme.getAll()).filter(theme => theme.type === "meta");
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
        qx.theme.manager.Meta.getInstance().setTheme(theme);
        window.localStorage.setItem("themeName", theme.name);
      }
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
