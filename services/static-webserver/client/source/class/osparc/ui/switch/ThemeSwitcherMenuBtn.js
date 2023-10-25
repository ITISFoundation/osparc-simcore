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

    if (!osparc.ui.switch.ThemeSwitcher.isSwitchUseful()) {
      this.setVisibility("excluded");
      return;
    }

    osparc.ui.switch.ThemeSwitcher.bindLabelToTheme(this);
    osparc.ui.switch.ThemeSwitcher.bindIconToTheme(this, 14);
    this.addListener("execute", () => osparc.ui.switch.ThemeSwitcher.switchTheme());
  }
});
