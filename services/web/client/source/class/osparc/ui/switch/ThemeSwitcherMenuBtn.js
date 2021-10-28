/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2021 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Switch button for controlling the theme
 */

qx.Class.define("osparc.ui.switch.ThemeSwitcherMenuBtn", {
  extend: qx.ui.menu.Button,

  construct: function() {
    this.base(arguments);

    const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.setLabel(this.tr("Switch theme"));

    this.addListener("execute", () => {
      osparc.ui.switch.ThemeSwitcher.switchTheme();
    });
    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => {
      osparc.ui.switch.ThemeSwitcher.updateIcon(this, 22);
    }, this);
    osparc.ui.switch.ThemeSwitcher.updateIcon(this, 22);
  }
});
