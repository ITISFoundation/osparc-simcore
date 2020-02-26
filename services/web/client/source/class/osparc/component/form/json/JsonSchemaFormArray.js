/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated form array to be used inside JsonSchemaForm.
 */
qx.Class.define("osparc.component.form.json.JsonSchemaFormArray", {
  extend: qx.ui.container.Composite,
  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox());
    this.__children = new qx.type.Array();
  },
  members: {
    __children: null,
    // overwritten
    add: function(child, options) {
      this.base(arguments, child, options);
      this.__children.push(child);
      if (this.getChildren().length === 1) {
        this.setAppearance("form-array-container");
      }
    },
    // overwritten
    remove(child) {
      this.base(arguments, child);
      this.__children.remove(child);
      if (!this.hasChildren()) {
        this.resetAppearance();
      }
    }
  }
});
