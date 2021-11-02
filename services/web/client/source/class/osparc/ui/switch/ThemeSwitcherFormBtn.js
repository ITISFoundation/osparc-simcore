/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2021 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Switch button for controlling the theme
 */

qx.Class.define("osparc.ui.switch.ThemeSwitcherFormBtn", {
  extend: qx.ui.form.Button,

  construct: function() {
    this.base(arguments);

    const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
    if (validThemes.length !== 2) {
      this.setVisibility("excluded");
      return;
    }

    this.addListener("execute", () => {
      osparc.ui.switch.ThemeSwitcher.switchTheme();
    });

    osparc.ui.switch.ThemeSwitcher.bindIconToTheme(this, 22);
  }
});
