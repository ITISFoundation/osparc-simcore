/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Generic confirmation window.
 * Provides "Cancel" and "Yes" buttons as well as boolean Confirmed property.
 */
qx.Class.define("osparc.ui.window.Confirmation", {
  extend: osparc.ui.window.Dialog,

  /**
   * @extends osparc.ui.window.Dialog
   * @param {String} message Message that will be displayed to the user.
   */
  construct: function(message) {
    this.base(arguments, this.tr("Confirmation"), null, message);

    this.addCancelButton();

    const btnYes = new qx.ui.toolbar.Button("Yes");
    osparc.utils.Utils.setIdToWidget(btnYes, "confirmDeleteStudyBtn");
    btnYes.addListener("execute", e => {
      this.setConfirmed(true);
      this.close(1);
    }, this);
    this.addButton(btnYes);
  },

  properties: {
    confirmed: {
      check: "Boolean",
      init: false
    }
  }
});
