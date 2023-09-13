/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated form array to be used inside JsonSchemaForm.
 */
qx.Class.define("osparc.form.json.JsonSchemaFormArray", {
  extend: qx.ui.container.Composite,
  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox());
  },
  members: {
    // overwritten
    add: function(child, options) {
      this.base(arguments, child, options);
      if (this.getChildren().length === 1) {
        this.setAppearance("form-array-container");
      }
      child.setKey(this.getChildren().length - 1);
    },
    // overwritten
    remove(child) {
      this.base(arguments, child);
      if (!this.hasChildren()) {
        this.resetAppearance();
      }
      const children = this.getChildren();
      for (let i=0; i<children.length; i++) {
        children[i].setKey(i);
      }
    }
  }
});
