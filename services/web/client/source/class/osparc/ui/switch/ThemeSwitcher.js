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

    const validThemes = Object.values(qx.Theme.getAll()).filter(theme => theme.type === "meta");
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.addListener("changeChecked", e => {
      if (e.getData()) {
        qx.theme.manager.Meta.getInstance().setTheme(qx.Theme.getByName("osparc.theme.ThemeLight"));
      } else {
        qx.theme.manager.Meta.getInstance().setTheme(qx.Theme.getByName("osparc.theme.ThemeDark"));
      }
    });
  }
});
