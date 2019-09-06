/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.ui.form.AutocompleteField", {
  extend: qx.ui.form.VirtualComboBox,

  construct: function(data) {
    this.base(arguments, data);
    this.__attachEventHandlers();
  },

  members: {
    __attachEventHandlers: function() {
    }
  }
});
