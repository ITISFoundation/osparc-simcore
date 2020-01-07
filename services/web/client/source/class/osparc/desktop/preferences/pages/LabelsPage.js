/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Preferences page for managing the user's labels.
 */
qx.Class.define("osparc.desktop.preferences.pages.LabelsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,
  construct: function() {
    this.base(arguments, this.tr("Label"), "@FontAwesome5Solid/tags/24");
  }
});
