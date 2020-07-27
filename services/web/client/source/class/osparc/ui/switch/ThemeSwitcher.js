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
  extend: osparc.ui.switch.Switch,

  construct: function() {
    this.base(arguments);

    const validThemes = [];
    const themes = qx.Theme.getAll();
    for (const key in themes) {
      const theme = themes[key];
      if (theme.type === "meta") {
        validThemes.push(theme);
      }
    }
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.addListener("changeChecked", () => {
      const themeMgr = qx.theme.manager.Meta.getInstance();
      const currentTheme = themeMgr.getTheme();
      if (currentTheme === validThemes[0]) {
        themeMgr.setTheme(validThemes[1]);
      } else {
        themeMgr.setTheme(validThemes[0]);
      }
    });
  }
});
