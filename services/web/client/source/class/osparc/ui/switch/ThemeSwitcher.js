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

    const validThemes = this.__validThemes = Object.values(qx.Theme.getAll()).filter(theme => theme.type === "meta");
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.set({
      checked: qx.theme.manager.Meta.getInstance().getTheme().name === validThemes[1].name,
      toolTipText: this.tr("Switch theme")
    });

    this.addListener("changeChecked", () => {
      this.__switchTheme();
    });
  },

  members: {
    __validThemes: null,

    __switchTheme: function() {
      if (this.__validThemes.length !== 2) {
        return;
      }

      const currentTheme = qx.theme.manager.Meta.getInstance().getTheme();
      const idx = this.__validThemes.findIndex(validTheme => validTheme.name === currentTheme.name);
      if (idx !== -1) {
        const theme = this.__validThemes[1-idx];
        qx.theme.manager.Meta.getInstance().setTheme(theme);
        window.localStorage.setItem("themeName", theme.name);
      }
    }
  }
});
