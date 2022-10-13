/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Form widget that simply extends SelectBox to avoid the manipulation of ``qx.ui.form.ListItem`` as menu options.
 */
qx.Class.define("osparc.ui.form.ListItemSelectBox", {
  extend: qx.ui.form.SelectBox,
  members: {
    // overwritten
    add: function(label, icon, model, options) {
      this.base(arguments, new qx.ui.form.ListItem(label, icon, model), options);
    },
    // overwritten
    getValue: function() {
      const listItem = this.base(arguments);
      return listItem.getLabel();
    },
    // overwritten
    setValue: function(value) {
      const item = this.getChildren().find(child => child.getLabel() === value);
      if (item) {
        this.base(arguments, item);
      }
    }
  }
});
